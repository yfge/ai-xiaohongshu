"""SQLAlchemy async engine and session utilities."""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings


@lru_cache
def get_async_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return create_async_engine(settings.database_url, echo=settings.database_echo, future=True)


@lru_cache
def get_session_maker(settings: Settings) -> async_sessionmaker:
    engine = get_async_engine(settings)
    return async_sessionmaker(engine, expire_on_commit=False)
