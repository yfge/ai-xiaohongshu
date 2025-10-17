"""Helpers for creating Ark runtime clients."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

try:  # pragma: no cover - optional dependency fallback for local dev/tests
    from volcenginesdkarkruntime import AsyncArk
except ModuleNotFoundError:  # pragma: no cover
    class AsyncArk:  # type: ignore[override]
        """Placeholder to surface a clear error if the SDK is missing at runtime."""

        def __init__(self, *_: object, **__: object) -> None:  # noqa: D401 - docstring above
            raise ModuleNotFoundError(
                "volcenginesdkarkruntime is required. Install the volcengine SDK to call Ark APIs."
            )

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
