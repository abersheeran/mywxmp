import asyncio
import base64
import time
from typing import Annotated, Literal

import httpx
from kui.asgi import Depends, HttpView, PlainTextResponse, Query, Routes, request
from loguru import logger

from .ai_api import GenerateNetworkError, GenerateResponseError, GenerateSafeError
from .ai_api.gemini import Content as GeminiRequestContent
from .ai_api.gemini import Part as GeminiRequestPart
from .ai_api.gemini import generate_content
from .dependencies import get_pending_queue, get_pending_queue_count, get_picture_cache
from .middlewares import validate_wechat_signature
from .settings import settings
from .xml import build_xml, parse_xml

routes = Routes()


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
        pending_queue: Annotated[
            dict[str, asyncio.Task[str]], Depends(get_pending_queue)
        ],
        pending_queue_count: Annotated[
            dict[str, int], Depends(get_pending_queue_count)
        ],
    ) -> Annotated[
        str | Literal[b""],
        PlainTextResponse[200],
    ]:
        xml = parse_xml((await request.body).decode("utf-8"))
        logger.debug(f"Received message: {xml}")
        msg_type = xml["MsgType"]
        user_id = xml["FromUserName"]

        match msg_type:
            case "event":
                match xml["Event"]:
                    case "subscribe":
                        return build_xml(
                            {
                                "ToUserName": user_id,
                                "FromUserName": settings.wechat_id,
                                "CreateTime": str(int(time.time())),
                                "MsgType": "text",
                                "Content": "欢迎关注我的微信公众号，我会在这里推送一些我写的小说，你也可以直接给我发送消息来和我进行 7×24 的对话。",
                            }
                        )
                    case "unsubscribe":
                        return b""
                    case _:
                        return b""
            case "image":
                picture_cache.setdefault(user_id, []).append(xml["PicUrl"])
                asyncio.get_running_loop().call_later(
                    60, picture_cache.pop, user_id, None
                )
                return b""
            case "text":
                if xml["Content"] == "【收到不支持的消息类型，暂无法显示】":
                    return build_xml(
                        {
                            "ToUserName": user_id,
                            "FromUserName": settings.wechat_id,
                            "CreateTime": str(int(time.time())),
                            "MsgType": "text",
                            "Content": "请不要发送表情包。",
                        }
                    )
                msg_id = xml["MsgId"]
                if msg_id in pending_queue:
                    pending_queue_count[msg_id] += 1
                    if pending_queue_count[msg_id] >= 3:
                        return await pending_queue[msg_id]
                    else:
                        return await asyncio.shield(pending_queue[msg_id])
                else:
                    pending_queue_count[msg_id] = 1
                    task = pending_queue[msg_id] = asyncio.create_task(
                        cls.generate_content(user_id, xml["Content"])
                    )
                    task.add_done_callback(
                        lambda future: (
                            pending_queue.pop(msg_id, None),
                            pending_queue_count.pop(msg_id, None),
                        )
                    )
                    return await asyncio.shield(pending_queue[msg_id])
            case "voice":
                if "Recognition" not in xml:
                    return build_xml(
                        {
                            "ToUserName": user_id,
                            "FromUserName": settings.wechat_id,
                            "CreateTime": str(int(time.time())),
                            "MsgType": "text",
                            "Content": "开发者未开启“接收语音识别结果”功能，请到公众平台官网“设置与开发”页的“接口权限”里开启。",
                        }
                    )
                if not xml["Recognition"]:
                    return build_xml(
                        {
                            "ToUserName": user_id,
                            "FromUserName": settings.wechat_id,
                            "CreateTime": str(int(time.time())),
                            "MsgType": "text",
                            "Content": "微信无法识别这条语音内容，请重新发送。",
                        }
                    )
                msg_id = xml["MsgId"]
                if msg_id in pending_queue:
                    pending_queue_count[msg_id] += 1
                    if pending_queue_count[msg_id] >= 3:
                        return await pending_queue[msg_id]
                    else:
                        return await asyncio.shield(pending_queue[msg_id])
                else:
                    pending_queue_count[msg_id] = 1
                    task = pending_queue[msg_id] = asyncio.create_task(
                        cls.generate_content(user_id, xml["Recognition"])
                    )
                    task.add_done_callback(
                        lambda future: (
                            pending_queue.pop(msg_id, None),
                            pending_queue_count.pop(msg_id, None),
                        )
                    )
                    return await asyncio.shield(pending_queue[msg_id])
            case _:
                return build_xml(
                    {
                        "ToUserName": user_id,
                        "FromUserName": settings.wechat_id,
                        "CreateTime": str(int(time.time())),
                        "MsgType": "text",
                        "Content": "暂不支持此消息类型。",
                    }
                )

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
            response_content = await generate_content(contents)
        except GenerateSafeError as error:
            response_content = "这是不可以谈的话题。"
            logger.warning(f"Safe error: {error}")
        except GenerateResponseError as error:
            response_content = error.message
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
