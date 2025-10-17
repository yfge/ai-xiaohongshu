"""API-level tests for marketing collage endpoint upload validation."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.deps import get_marketing_service
from app.main import app


class _FailingService:
    async def generate_collage(self, **_: object):  # type: ignore[override]
        raise AssertionError("service should not be invoked for invalid uploads")


@pytest.fixture(name="client")
def client_fixture() -> TestClient:
    app.dependency_overrides[get_marketing_service] = lambda: _FailingService()  # type: ignore[return-value]
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_marketing_service, None)


def test_generate_collage_rejects_non_image_upload(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(ark_api_key="test")
    response = client.post(
        "/api/marketing/collage",
        data={"prompt": "test", "count": "1"},
        files={"images": ("demo.txt", b"hello", "text/plain")},
    )
    app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 400
    assert "不是支持的图片格式" in response.json()["detail"]


def test_generate_collage_rejects_oversized_upload(client: TestClient) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        collage_upload_max_bytes=8,
    )
    response = client.post(
        "/api/marketing/collage",
        data={"prompt": "test", "count": "1"},
        files={"images": ("demo.png", b"0123456789", "image/png")},
    )
    app.dependency_overrides.pop(get_settings, None)

    assert response.status_code == 413
    assert "单张图片大小不能超过" in response.json()["detail"]
