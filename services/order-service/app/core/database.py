#This file initializes the asynchronous connection pool. 
#We use AsyncSession and create_async_engine.

from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

DATABASE_URL = "postgresql+asyncpg://user:password@localhost:5432/dbname"

# pool_size and max_overflow are critical for highly concurrent apps
engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,          # Keeps 20 persistent connections open per worker
    max_overflow=10,       # Allows 10 temporary extra connections under spikes
    pool_timeout=30,       # Fails fast if connection cannot be acquired
    pool_pre_ping=True     # Checks if connection is alive before using it
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine, 
    class_=AsyncSession, 
    expire_on_commit=False  # Prevents unnecessary DB re-fetches after commits
)

Base = declarative_base()

# Dependency injector for FastAPI routes
async def get_async_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close() # Ensures connection goes back to the pool
