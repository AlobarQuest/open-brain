from functools import lru_cache

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    from src.config import get_settings
    s = get_settings()
    return create_async_engine(
        s.database_url,
        echo=s.app_env == "development",
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        pool_pre_ping=True,
    )


@lru_cache
def get_session_factory():
    return async_sessionmaker(
        get_engine(),
        expire_on_commit=False,
        autoflush=False,
    )
