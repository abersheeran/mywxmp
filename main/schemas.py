from pydantic import BaseModel


class WechatQrCodeEntity(BaseModel):
    ticket: str
    expire_seconds: int
    url: str
