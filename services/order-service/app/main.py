from fastapi import FastAPI
from app.routes import router

#FastAPI app + router includes
app = FastAPI(title="order-service")
app.include_router(router)

@app.get("/")
async def root():
    return {"message": "order API"}