from fastapi import FastAPI
from app.routes.order_router import router

app = FastAPI(title="order-service")
app.include_router(router)


@app.get("/")
async def root():
    return {"message": "order API"}
