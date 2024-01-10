from typing import Annotated

from kui.asgi import Depends, HttpView, Routes, request

from .dependencies import wechat_echostr
from .xml import parse_xml

routes = Routes()


@routes.http("/wechat")
class Wechat(HttpView):
    async def get(self, echostr: Annotated[str, Depends(wechat_echostr)]):
        return echostr

    async def post(self, echostr: Annotated[str, Depends(wechat_echostr)]):
        xml = parse_xml((await request.body).decode("utf-8"))
        return b""
