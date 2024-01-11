from functools import wraps
from typing import Any, Awaitable, Callable, Coroutine, ParamSpec, TypeVar

R = TypeVar("R")
P = ParamSpec("P")


def retry_when_exception(*exceptions: type[BaseException], max_tries: int = 3):
    def d(func: Callable[P, Awaitable[R]]) -> Callable[P, Coroutine[Any, Any, R]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            for i in range(max_tries):
                try:
                    return await func(*args, **kwargs)
                except exceptions:
                    if i == max_tries - 1:
                        raise
            raise RuntimeError("Unreachable")

        return wrapper

    return d
