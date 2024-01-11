import asyncio
import base64
import time
from typing import Annotated

import httpx
from kui.asgi import Depends, HttpView, Query, Routes, request
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
class Wechat(HttpView):
    @classmethod
    async def get(cls, echostr: Annotated[str, Query(...)]):
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
    ):
        xml = parse_xml((await request.body).decode("utf-8"))
        msg_id = xml["MsgId"]
        msg_type = xml["MsgType"]
        user_id = xml["FromUserName"]

        match msg_type:
            case "text":
                if msg_id in pending_queue:
                    pending_queue_count[msg_id] += 1
                    if pending_queue_count[msg_id] >= 3:
                        return await pending_queue[msg_id]
                    else:
                        return await asyncio.shield(pending_queue[msg_id])
                else:
                    pending_queue_count[msg_id] = 1
                    pending_queue[msg_id] = asyncio.create_task(
                        cls.generate_content(user_id, msg_id, xml["Content"])
                    )
                    return await asyncio.shield(pending_queue[msg_id])
            case "image":
                picture_cache.setdefault(user_id, []).append(xml["PicUrl"])
                asyncio.get_running_loop().call_later(
                    60, picture_cache.pop, user_id, None
                )
                return b""

    @classmethod
    async def generate_content(cls, user_id: str, message_id: str, message_text: str):
        parts: list[GeminiRequestPart] = [{"text": message_text}]
        photos: list[str] = get_picture_cache().pop(message_id, [])
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
