import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base


POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://aria:aria@localhost:5432/aria")
ASYNC_DATABASE_URL = POSTGRES_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(ASYNC_DATABASE_URL, future=True)
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)
Base = declarative_base()


async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()
