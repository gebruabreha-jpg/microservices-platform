import logging
from fastapi import FastAPI
from app.routes.order_router import router
from shared.telemetry import setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("order-service")

app = FastAPI(title="order-service")
app.include_router(router)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    setup_tracing("order-service")
    FastAPIInstrumentor.instrument_app(app)
except ImportError:
    pass

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_ipaddr
    from slowapi.errors import RateLimitExceeded
    limiter = Limiter(key_func=get_ipaddr, default_limits=["100/minute"])
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
except ImportError:
    pass


@app.get("/")
async def root():
    return {"message": "order API"}


@app.on_event("shutdown")
def shutdown():
    logger.info("Shutting down order-service")
