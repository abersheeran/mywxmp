import asyncio
import base64
import time
from typing import Annotated, Any, Literal

import httpx
from kui.asgi import (
    Body,
    Depends,
    Header,
    HTTPException,
    HttpView,
    JSONResponse,
    PlainTextResponse,
    Query,
    Routes,
    api_key_auth_dependency,
    request,
)
from loguru import logger
from pydantic import HttpUrl

from .ai_api import GenerateNetworkError, GenerateResponseError, GenerateSafeError
from .ai_api.gemini import Content as GeminiRequestContent
from .ai_api.gemini import Part as GeminiRequestPart
from .ai_api.gemini import generate_content
from .dependencies import (
    get_access_token,
    get_pending_queue,
    get_pending_queue_count,
    get_picture_cache,
)
from .middlewares import validate_github_signature, validate_wechat_signature
from .schemas import WechatQrCodeEntity
from .settings import settings
from .xml import build_xml, parse_xml

routes = Routes()


@routes.http.post("/qrcode")
async def create_wechat_qrcode(
    api_key: Annotated[str, Depends(api_key_auth_dependency("api-key"))],
    callback: Annotated[HttpUrl, Body(...)],
) -> Annotated[Any, JSONResponse[201, {}, WechatQrCodeEntity]]:
    if settings.qrcode_api_token != api_key:
        raise HTTPException(401)

    payload = {
        "action_name": "QR_STR_SCENE",
        "expire_seconds": 60 * 10,
        "action_info": {
            "scene": {"scene_str": str(callback)},
        },
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/qrcode/create",
            params={"access_token": await get_access_token()},
            json=payload,
        )
        resp.raise_for_status()
        qrcode = resp.json()
        logger.debug(f"Generate WeChat QR code: {qrcode}")

    return (
        WechatQrCodeEntity(
            ticket=qrcode["ticket"],
            expire_seconds=qrcode["expire_seconds"],
            url=qrcode["url"],
        ),
        201,
    )


@routes.http("/wechat", middlewares=[validate_wechat_signature])
class WeChat(HttpView):
    @classmethod
    async def get(
        cls, echostr: Annotated[str, Query(...)]
    ) -> Annotated[
        str,
        PlainTextResponse[200],
    ]:
        return echostr

    @classmethod
    async def post(
        cls,
        picture_cache: Annotated[dict[str, list[str]], Depends(get_picture_cache)],
    ) -> Annotated[
        str | Literal[b""],
        PlainTextResponse[200],
    ]:
        text = (await request.body).decode("utf-8")
        xml = parse_xml(text)
        logger.debug(f"Received message: {xml}\n{text}")
        msg_type = xml["MsgType"]

        match msg_type:
            case "event":
                return await cls.handle_event(xml)
            case "image":
                user_id = xml["FromUserName"]
                picture_cache.setdefault(user_id, []).append(xml["PicUrl"])
                asyncio.get_running_loop().call_later(
                    60, picture_cache.pop, user_id, None
                )
                return b""
            case "text":
                return await cls.handle_text(xml)
            case "voice":
                return await cls.handle_voice(xml)
            case _:
                user_id = xml["FromUserName"]
                return cls.reply_text(user_id, "暂不支持此消息类型。")

    @classmethod
    async def handle_event(cls, xml: dict[str, str]) -> str | Literal[b""]:
        if xml["EventKey"] and xml["Event"] in ("subscribe", "scan"):
            return await cls.handle_scan_callback(xml)

        match xml["Event"]:
            case "subscribe":
                return await cls.handle_event_subscribe(xml)
            case _:
                return b""

    @classmethod
    async def handle_event_subscribe(cls, xml: dict[str, str]) -> str:
        return cls.reply_text(
            xml["FromUserName"],
            "欢迎关注我的微信公众号，我会在这里推送一些我写的小说。你可以直接给我发送消息来和我进行 7×24 的对话。",
        )

    @classmethod
    async def handle_scan_callback(cls, xml: dict[str, str]) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                xml["EventKey"],
                json={
                    "openid": xml["FromUserName"],
                    "create_time": xml["CreateTime"],
                },
            )
            response.raise_for_status()
            if xml["Event"] == "subscribe":
                return await cls.handle_event_subscribe(xml)
            return cls.reply_text(xml["FromUserName"], "扫码成功。")

    @classmethod
    async def handle_text(cls, xml: dict[str, str]) -> str:
        user_id = xml["FromUserName"]
        msg_id = xml["MsgId"]
        content = xml["Content"]
        if content == "【收到不支持的消息类型，暂无法显示】":
            return cls.reply_text(user_id, "请不要发送表情包。")
        return await cls.wait_generate_content(user_id, msg_id, content)

    @classmethod
    async def handle_voice(cls, xml: dict[str, str]) -> str:
        user_id = xml["FromUserName"]
        if "Recognition" not in xml:
            return cls.reply_text(
                user_id,
                "开发者未开启“接收语音识别结果”功能，请到公众平台官网“设置与开发”页的“接口权限”里开启。",
            )
        if not xml["Recognition"]:
            return cls.reply_text(user_id, "微信无法识别这条语音内容，请重新发送。")
        msg_id = xml["MsgId"]
        content = xml["Recognition"]
        return await cls.wait_generate_content(user_id, msg_id, content)

    @staticmethod
    def reply_text(user_id: str, content: str) -> str:
        """
        https://developers.weixin.qq.com/doc/offiaccount/Message_Management/Passive_user_reply_message.html
        """
        return build_xml(
            {
                "ToUserName": user_id,
                "FromUserName": settings.wechat_id,
                "CreateTime": str(int(time.time())),
                "MsgType": "text",
                "Content": content,
            }
        )

    @classmethod
    async def wait_generate_content(
        cls, user_id: str, msg_id: str, content: str
    ) -> str:
        pending_queue = get_pending_queue()
        pending_queue_count = get_pending_queue_count()

        if msg_id in pending_queue:
            pending_queue_count[msg_id] += 1
            if pending_queue_count[msg_id] >= 3:
                return await pending_queue[msg_id]
            else:
                return await asyncio.shield(pending_queue[msg_id])
        else:
            pending_queue_count[msg_id] = 1
            pending_queue[msg_id] = asyncio.create_task(
                cls.generate_content(user_id, content)
            )
            asyncio.get_running_loop().call_later(
                20,
                lambda: (
                    pending_queue.pop(msg_id, None),
                    pending_queue_count.pop(msg_id, None),
                ),
            )
            return await asyncio.shield(pending_queue[msg_id])

    @classmethod
    async def generate_content(cls, user_id: str, message_text: str):
        parts: list[GeminiRequestPart] = [{"text": message_text}]
        photos: list[str] = get_picture_cache().pop(user_id, [])
        async with httpx.AsyncClient() as client:
            for photo_url in photos:
                resp = await client.get(photo_url)
                if not resp.is_success:
                    return "微信图片服务器出现问题，请稍后再试。"
                image = resp.content
                image_base64 = base64.b64encode(image).decode("utf-8")
                parts.append(
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": image_base64,
                        }
                    }
                )
        contents: list[GeminiRequestContent] = [{"parts": parts}]
        try:
            response_content = await generate_content(
                contents, safety_threshold="BLOCK_MEDIUM_AND_ABOVE"
            )
        except GenerateSafeError as error:
            response_content = "这是不可以谈的话题。"
            logger.warning(f"Safe error: {error}")
        except GenerateResponseError as error:
            response_content = "我好像找不到我的大脑了。"
            logger.exception(f"Response error: {error}")
        except GenerateNetworkError as error:
            response_content = "网络出现问题，请稍后再试。"
            logger.warning(f"Network error: {error}")

        # <xml>
        # <ToUserName><![CDATA[toUser]]></ToUserName>
        # <FromUserName><![CDATA[fromUser]]></FromUserName>
        # <CreateTime>12345678</CreateTime>
        # <MsgType><![CDATA[text]]></MsgType>
        # <Content><![CDATA[你好]]></Content>
        # </xml>
        return build_xml(
            {
                "ToUserName": user_id,
                "FromUserName": settings.wechat_id,
                "CreateTime": str(int(time.time())),
                "MsgType": "text",
                "Content": response_content,
            }
        )


@routes.http("/github", middlewares=[validate_github_signature])
class GitHub(HttpView):
    @classmethod
    async def post(
        cls,
        github_event_type: Annotated[str, Header(..., alias="X-GitHub-Event")],
    ):
        match github_event_type:
            case "ping":
                return "pong"
            case "push":
                # TODO
                return "OK"
            case _:
                return "Unsupported event type.", 400
