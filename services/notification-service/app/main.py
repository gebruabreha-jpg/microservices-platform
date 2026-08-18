from fastapi import FastAPI
from app.routes.notification_router import router
import threading
from app.service.notification_service import start_consumer

app = FastAPI(title="notification-service")
app.include_router(router)

consumer_thread = threading.Thread(target=start_consumer, daemon=True)
consumer_thread.start()
