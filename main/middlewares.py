import hashlib
from typing import Annotated, Any

from cool import F
from kui.asgi import HTTPException, PlainTextResponse, Query

from .settings import settings


def validate_wechat_signature(endpoint):
    """
    https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Access_Overview.html
    """

    async def w(
        signature: Annotated[str, Query(...)],
        timestamp: Annotated[str, Query(...)],
        nonce: Annotated[str, Query(...)],
    ) -> Annotated[Any, PlainTextResponse[400]]:
        string = [settings.wechat_token, timestamp, nonce] | F(sorted) | F("".join)
        sha1 = string.encode("utf-8") | F(lambda x: hashlib.sha1(x).hexdigest())
        if sha1 != signature:
            raise HTTPException(400, content="Invalid signature")
        return await endpoint()

    return w
