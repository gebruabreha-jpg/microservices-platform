from fastapi import FastAPI
from app.routes import router as order-router

#FastAPI app + router includes
app = FastAPI(title="order-service")
app.include_router(order-router)

@app.get("/")
async def root():
    return {"message": "order API"}