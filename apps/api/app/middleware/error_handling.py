"""Uniform error responses + server-side logging.

Every error response has the same shape: `{"error": <code>, "detail": ...,
"request_id": ...}`. Unhandled exceptions are logged with their full
traceback server-side but never leak internals (stack traces, exception
messages that might contain secrets) to the client — the client only ever
sees "internal_server_error" plus the request ID to hand to support.
"""

import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.request_context import get_request_id

logger = logging.getLogger("opero.errors")


def _error_response(status_code: int, error: str, detail: object) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail, "request_id": get_request_id()},
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(exc.status_code, error=exc.__class__.__name__, detail=exc.detail)


async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _error_response(
        status.HTTP_422_UNPROCESSABLE_ENTITY, error="validation_error", detail=exc.errors()
    )


async def handle_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        error="internal_server_error",
        detail="An unexpected error occurred. Include the request ID when reporting this.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    # Both are registered: Starlette's routing layer (404s, method-not-allowed)
    # raises the base StarletteHTTPException directly, while FastAPI's own
    # HTTPException (raised inside route handlers/dependencies) is a subclass —
    # Starlette's handler lookup does not treat the subclass registration as
    # covering the base class.
    app.add_exception_handler(StarletteHTTPException, handle_http_exception)
    app.add_exception_handler(HTTPException, handle_http_exception)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(Exception, handle_unhandled_exception)
