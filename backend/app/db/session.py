"""SQLAlchemy async engine and session utilities."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import Settings


@lru_cache
def _get_async_engine(database_url: str, database_echo: bool) -> AsyncEngine:
    return create_async_engine(database_url, echo=database_echo, future=True)


@lru_cache
def _get_session_maker(database_url: str, database_echo: bool) -> async_sessionmaker:
    engine = _get_async_engine(database_url, database_echo)
    return async_sessionmaker(engine, expire_on_commit=False)


def get_async_engine(settings: Settings) -> AsyncEngine:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return _get_async_engine(settings.database_url, settings.database_echo)


def get_session_maker(settings: Settings) -> async_sessionmaker:
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not configured")
    return _get_session_maker(settings.database_url, settings.database_echo)
