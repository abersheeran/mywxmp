from typing import Annotated

from kui.asgi import HttpView, Query, Routes, request

from .middlewares import validate_wechat_signature
from .xml import parse_xml

routes = Routes()


@routes.http("/wechat", middlewares=[validate_wechat_signature])
class Wechat(HttpView):
    @classmethod
    async def get(cls, echostr: Annotated[str, Query(...)]):
        return echostr

    @classmethod
    async def post(cls):
        xml = parse_xml((await request.body).decode("utf-8"))
        return b""
