"""Tests for the marketing collage workflow."""
from __future__ import annotations

import json
from contextlib import asynccontextmanager

import pytest

pytestmark = pytest.mark.anyio("asyncio")

from app.core.config import Settings
from app.schemas.marketing import MarketingGenerationResponse
from app.services import marketing
from app.services.marketing import (
    ArkConfigurationError,
    ArkServiceError,
    MarketingCollageService,
    UploadedImage,
)


class _StubChatCompletions:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def create(self, **_: object):  # type: ignore[override]
        return _StubChatResponse(self._payload)


class _StubChat:
    def __init__(self, payload: dict) -> None:
        self.completions = _StubChatCompletions(payload)


class _StubImages:
    def __init__(self, image_url: str, b64: str, size: str) -> None:
        self._image_url = image_url
        self._b64 = b64
        self._size = size

    async def generate(self, **_: object):  # type: ignore[override]
        return _StubImageResponse(self._image_url, self._b64, self._size)


class _StubArk:
    def __init__(self, payload: dict) -> None:
        self.chat = _StubChat(payload)
        self.images = _StubImages(
            image_url="https://ark.fake/image.png",
            b64="ZmFrZS1pbWFnZS1ieXRlcw==",
            size="1024x1024",
        )

    async def close(self) -> None:  # pragma: no cover - compatibility
        return None


class _StubChatResponse:
    def __init__(self, payload: dict) -> None:
        self.choices = [_StubChoice(payload)]


class _StubChoice:
    def __init__(self, payload: dict) -> None:
        self.message = _StubMessage(payload)


class _StubMessage:
    def __init__(self, payload: dict) -> None:
        self.content = json.dumps(payload)


class _StubImageResponse:
    class _Image:
        def __init__(self, url: str, b64: str, size: str) -> None:
            self.url = url
            self.b64_json = b64
            self.size = size

    def __init__(self, url: str, b64: str, size: str) -> None:
        self.data = [self._Image(url, b64, size)]


async def test_generate_collage_success(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {
        "prompts": [
            {
                "title": "秋日氛围感",
                "prompt": "autumn style prompt",
                "description": "温柔通透的秋日生活方式",
                "hashtags": ["秋日穿搭", "氛围感"],
            }
        ]
    }

    @asynccontextmanager
    async def fake_client(_: Settings):
        client = _StubArk(payload)
        yield client

    monkeypatch.setattr(marketing, "async_ark_client", fake_client)

    settings = Settings(ark_api_key="test", ark_prompt_max_count=3)
    service = MarketingCollageService(settings)
    uploaded = [
        UploadedImage(filename="demo.png", content_type="image/png", data=b"fake-bytes")
    ]

    result = await service.generate_collage(brief="秋日穿搭", count=1, uploaded_images=uploaded)
    assert isinstance(result, MarketingGenerationResponse)
    assert len(result.prompts) == 1
    assert result.prompts[0].prompt == "autumn style prompt"
    assert len(result.images) == 1
    assert result.images[0].image_url.endswith("image.png")
    assert result.images[0].image_base64 == "ZmFrZS1pbWFnZS1ieXRlcw=="


async def test_generate_collage_raises_when_missing_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def fake_client(_: Settings):
        yield _StubArk({})

    monkeypatch.setattr(marketing, "async_ark_client", fake_client)

    settings = Settings(ark_api_key=None, ark_ak=None, ark_sk=None)
    service = MarketingCollageService(settings)
    uploaded = [
        UploadedImage(filename="demo.png", content_type="image/png", data=b"bytes")
    ]

    with pytest.raises(ArkConfigurationError):
        await service.generate_collage(brief="test", count=1, uploaded_images=uploaded)


async def test_generate_collage_exceeds_max_count(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def fake_client(_: Settings):
        yield _StubArk({"prompts": []})

    monkeypatch.setattr(marketing, "async_ark_client", fake_client)

    settings = Settings(ark_api_key="test", ark_prompt_max_count=2)
    service = MarketingCollageService(settings)
    uploaded = [
        UploadedImage(filename="demo.png", content_type="image/png", data=b"bytes")
    ]

    with pytest.raises(ArkServiceError):
        await service.generate_collage(brief="test", count=3, uploaded_images=uploaded)
