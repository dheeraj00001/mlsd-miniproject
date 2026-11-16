"""Correlation ID tracking across HTTP and background execution contexts (D5)."""

import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_correlation_id_ctx: ContextVar[str] = ContextVar("correlation_id", default="")


def get_correlation_id() -> str:
    """Retrieve current correlation ID or generate fallback."""
    cid = _correlation_id_ctx.get()
    if not cid:
        cid = f"corr-{uuid.uuid4().hex[:12]}"
        _correlation_id_ctx.set(cid)
    return cid


def set_correlation_id(correlation_id: str) -> None:
    """Explicitly set current correlation ID in context."""
    _correlation_id_ctx.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """FastAPI/Starlette middleware propagating X-Correlation-ID across HTTP lifecycles."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        cid = request.headers.get("X-Correlation-ID") or f"corr-{uuid.uuid4().hex[:12]}"
        _correlation_id_ctx.set(cid)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response
