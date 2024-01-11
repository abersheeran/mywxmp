import asyncio

from kui.asgi import request


def get_picture_cache() -> dict[str, list[str]]:
    return request.app.state.picture_cache


def get_pending_queue() -> dict[str, asyncio.Task[str]]:
    return request.app.state.pending_queue


def get_pending_queue_count() -> dict[str, int]:
    return request.app.state.pending_queue_count
