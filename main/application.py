import asyncio

import httpx
from kui.asgi import Kui
from loguru import logger

from .ai_api.gemini import initial_gemini_config
from .routes import routes
from .settings import settings

app = Kui()
app.router <<= routes


@app.on_startup
async def initial_gemini(app: Kui) -> None:
    await initial_gemini_config(
        settings.gemini_pro_key,
        pro_url=settings.gemini_pro_url,
        pro_vision_url=settings.gemini_pro_vision_url,
    )


@app.on_startup
async def initial_cache(app: Kui) -> None:
    app.state.picture_cache = {}
    app.state.pending_queue = {}
    app.state.pending_queue_count = {}


@app.on_startup
async def initial_token(app: Kui) -> None:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://api.weixin.qq.com/cgi-bin/token",
            params={
                "grant_type": "client_credential",
                "appid": settings.app_id,
                "secret": settings.app_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        app.state.access_token = data["access_token"]
        expires_in = data["expires_in"]

    task = asyncio.create_task(asyncio.sleep(expires_in - 60))
    task.add_done_callback(lambda future: asyncio.create_task(initial_token(app)))


@app.on_startup
async def initial_menus(app: Kui) -> None:
    menus = {
        "button": [
            {"name": "拍照上传", "type": "pic_photo_or_album", "key": "pzsc"},
            {
                "name": "发图",
                "sub_button": [
                    {
                        "type": "pic_sysphoto",
                        "name": "系统拍照发图",
                        "key": "rselfmenu_1_0",
                        "sub_button": [],
                    },
                    {
                        "type": "pic_photo_or_album",
                        "name": "拍照或者相册发图",
                        "key": "rselfmenu_1_1",
                        "sub_button": [],
                    },
                    {
                        "type": "pic_weixin",
                        "name": "微信相册发图",
                        "key": "rselfmenu_1_2",
                        "sub_button": [],
                    },
                ],
            },
        ]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.weixin.qq.com/cgi-bin/menu/create",
            params={"access_token": app.state.access_token},
            json=menus,
        )
        resp.raise_for_status()
        logger.info(f"Initial menus {menus} response: {resp}")
