from kui.asgi import Kui

from .routes import routes

app = Kui(routes=routes)
