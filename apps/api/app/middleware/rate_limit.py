"""Rate-limiting foundation (docs/SECURITY_MODEL.md §9).

A fixed-window limiter keyed by client IP, backed by Redis (INCR + EXPIRE).
This is the hook, not tuned thresholds — `rate_limit_per_minute` is a single
config value until there's real traffic data to size it against.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import get_settings
from app.core.redis_client import get_redis_client


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._limit = get_settings().rate_limit_per_minute

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Liveness/readiness probes are hit frequently by infra and shouldn't count
        # against a client's own rate limit.
        if request.url.path in ("/healthz", "/readyz"):
            return await call_next(request)

        redis_client = get_redis_client()
        client_ip = request.client.host if request.client else "unknown"
        window = int(time.time() // 60)
        key = f"ratelimit:{client_ip}:{window}"

        current = await redis_client.incr(key)
        if current == 1:
            await redis_client.expire(key, 60)

        if current > self._limit:
            return JSONResponse(
                status_code=429,
                content={"error": "rate_limited", "detail": "Too many requests.", "request_id": None},
            )

        return await call_next(request)
