import logging
from fastapi import FastAPI
from app.routes.notification_router import router
import threading
from app.service.notification_service import start_consumer, start_dlq_consumer
from shared.telemetry import setup_tracing

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("notification-service")

app = FastAPI(title="notification-service")
app.include_router(router)

try:
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    setup_tracing("notification-service")
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

consumer_thread = threading.Thread(target=start_consumer, daemon=True)
consumer_thread.start()

dlq_thread = threading.Thread(target=start_dlq_consumer, daemon=True)
dlq_thread.start()


@app.get("/")
async def root():
    return {"message": "notification API"}


@app.on_event("shutdown")
def shutdown():
    logger.info("Shutting down notification-service")
