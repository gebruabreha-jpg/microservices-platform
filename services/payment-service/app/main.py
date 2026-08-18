import logging
from fastapi import FastAPI
from app.routes.payment_router import router
import threading
from app.service.payment_service import start_kafka_consumer
from shared.telemetry import setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("payment-service")

app = FastAPI(title="payment-service")
app.include_router(router)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    setup_tracing("payment-service")
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

consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
consumer_thread.start()


@app.get("/")
async def root():
    return {"message": "payment API"}


@app.on_event("shutdown")
def shutdown():
    logger.info("Shutting down payment-service")
