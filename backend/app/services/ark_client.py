"""Helpers for creating Ark runtime clients."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from volcenginesdkarkruntime import AsyncArk

from app.core.config import Settings


@asynccontextmanager
async def async_ark_client(settings: Settings) -> AsyncIterator[AsyncArk]:
    """Yield an `AsyncArk` client configured from settings and ensure cleanup."""

    client = AsyncArk(
        api_key=settings.ark_api_key,
        ak=settings.ark_ak,
        sk=settings.ark_sk,
        base_url=settings.ark_base_url,
        timeout=settings.ark_request_timeout,
    )
    try:
        yield client
    finally:
        await client.close()
