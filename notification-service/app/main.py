from fastapi import FastAPI
import requests
import os

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "service": "notification-service"}


@app.get("/metrics")
def metrics():
    return {"service": "notification-service"}


@app.post("/notifications")
def send_notification(notification: dict):
    return {"id": 1, "status": "queued", "type": notification.get("type")}