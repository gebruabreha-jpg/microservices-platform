"""
Shared rate limiting.

Registers slowapi on a FastAPI app so the default limit is actually enforced:
the limiter object, the 429 handler, AND the middleware that applies the
default limit to every route (without the middleware the default is inert).
"""

import os


def setup_rate_limiting(app, logger=None):
    """Wire slowapi onto ``app``. No-op (with a warning) if slowapi is missing."""
    try:
        from slowapi import Limiter, _rate_limit_exceeded_handler
        from slowapi.errors import RateLimitExceeded
        from slowapi.middleware import SlowAPIMiddleware

        try:
            from slowapi.util import get_remote_address as key_func
        except ImportError:  # older slowapi
            from slowapi.util import get_ipaddr as key_func
    except ImportError:
        if logger is not None:
            logger.warning("slowapi not installed, rate limiting disabled")
        return None

    default_limit = os.getenv("RATE_LIMIT", "100/minute")
    limiter = Limiter(key_func=key_func, default_limits=[default_limit])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    return limiter
