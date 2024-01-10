import hashlib
from typing import Annotated

from cool import F
from kui.asgi import HTTPException, PlainTextResponse, Query

from .settings import settings


def wechat_echostr(
    signature: Annotated[str, Query(...)],
    timestamp: Annotated[str, Query(...)],
    nonce: Annotated[str, Query(...)],
    echostr: Annotated[str, Query(...)],
) -> Annotated[str, PlainTextResponse[400]]:
    """
    https://developers.weixin.qq.com/doc/offiaccount/Basic_Information/Access_Overview.html
    """
    string = [settings.wechat_token, timestamp, nonce] | F(sorted) | F("".join)
    sha1 = string.encode("utf-8") | F(lambda x: hashlib.sha1(x).hexdigest())
    if sha1 != signature:
        raise HTTPException(400, content="Invalid signature")
    return echostr
