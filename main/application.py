from kui.asgi import Kui

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
