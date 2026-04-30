import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT") == "production" or os.getenv("ARIA_ENV") == "production"


def _database_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL")
    if not url:
        if _is_production():
            raise RuntimeError("DATABASE_URL or POSTGRES_URL is required in production.")
        return "postgresql://aria:aria@localhost:5432/aria"

    if _is_production() and ("localhost" in url or "127.0.0.1" in url):
        raise RuntimeError("DATABASE_URL/POSTGRES_URL must not point to localhost in production.")

    return url


POSTGRES_URL = _database_url()
if POSTGRES_URL.startswith("postgres://"):
    ASYNC_DATABASE_URL = POSTGRES_URL.replace("postgres://", "postgresql+asyncpg://", 1)
else:
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
