import hashlib
import hmac
from typing import Annotated, Any

from cool import F
from kui.asgi import Header, HTTPException, PlainTextResponse, Query, request

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


def validate_github_signature(endpoint):
    """
    https://docs.github.com/en/developers/webhooks-and-events/securing-your-webhooks
    """

    async def w(
        signature_header: Annotated[str, Header(..., alias="X-Hub-Signature-256")]
    ) -> None:
        """Verify that the payload was sent from GitHub by validating SHA256.

        Raise and return 403 if not authorized.
        """
        if not signature_header:
            raise HTTPException(
                status_code=403, content="x-hub-signature-256 header is missing!"
            )
        hash_object = hmac.new(
            settings.github_webhook_secret.encode("utf-8"),
            msg=await request.body,
            digestmod=hashlib.sha256,
        )
        expected_signature = "sha256=" + hash_object.hexdigest()
        if not hmac.compare_digest(expected_signature, signature_header):
            raise HTTPException(
                status_code=403, content="Request signatures didn't match!"
            )
        return await endpoint()

    return w
