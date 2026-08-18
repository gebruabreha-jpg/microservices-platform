from fastapi import FastAPI
from app.routes.payment_router import router
import threading
from app.service.payment_service import start_kafka_consumer

app = FastAPI(title="payment-service")
app.include_router(router)

consumer_thread = threading.Thread(target=start_kafka_consumer, daemon=True)
consumer_thread.start()
