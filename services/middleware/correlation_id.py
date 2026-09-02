"""
Shared FastAPI middleware.

Middleware intercepts HTTP requests and responses. Unlike shared utilities
(tracing, metrics, logging), middleware is specifically designed to wrap
the request/response lifecycle.
"""

import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from shared.observability import get_logger

logger = get_logger("middleware")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Extract or generate a correlation ID for request tracing.

    If the client provides an 'X-Correlation-ID' header, it is used.
    Otherwise, a new UUID is generated. The correlation ID is stored in
    request.state and added to the response headers.

    Usage:
        app.add_middleware(CorrelationIdMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = correlation_id

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = correlation_id

        logger.info(f"{request.method} {request.url.path}", correlation_id=correlation_id)
        return response
