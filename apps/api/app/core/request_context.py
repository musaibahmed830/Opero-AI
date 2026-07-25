"""A contextvar carrying the current request's ID, set by
app/middleware/request_id.py and read by app/core/logging.py — this is what
lets every log line in a request be correlated without threading the ID
through every function signature.
"""

from contextvars import ContextVar

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def set_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def get_request_id() -> str | None:
    return _request_id.get()
