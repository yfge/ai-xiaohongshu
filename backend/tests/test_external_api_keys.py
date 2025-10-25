"""Tests for external API using API keys and admin Basic auth for key issuance."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.deps import get_marketing_service
from app.main import app
from app.schemas.marketing import GeneratedImage, MarketingGenerationResponse, PromptVariant


class _StubService:
    async def generate_collage(self, **_: object) -> MarketingGenerationResponse:  # type: ignore[override]
        pv = PromptVariant(title="t", prompt="p", description=None, hashtags=["a", "b"])
        return MarketingGenerationResponse(
            prompts=[pv],
            images=[GeneratedImage(prompt=pv, image_url="https://img/x.png", image_base64=None, size="1024x1024")],
        )


@pytest.fixture(name="client")
def client_fixture(tmp_path: Path) -> TestClient:
    app.dependency_overrides[get_marketing_service] = lambda: _StubService()  # type: ignore[return-value]
    store_path = tmp_path / "api_keys.jsonl"
    audit_path = tmp_path / "audit.jsonl"
    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        api_key_store_path=str(store_path),
        audit_log_store_path=str(audit_path),
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
    )
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_marketing_service, None)
    app.dependency_overrides.pop(get_settings, None)


def _basic_auth(username: str, password: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_issue_api_key_and_call_external(client: TestClient, tmp_path: Path) -> None:
    # Create key via admin
    resp = client.post(
        "/api/admin/api-keys",
        json={"name": "ci", "scopes": ["marketing:collage"]},
        headers=_basic_auth("admin", "secret"),
    )
    assert resp.status_code == 200
    key = resp.json()["api_key"]
    assert "." in key

    # Use the key to call external endpoint
    files = {"images": ("foo.png", b"1234", "image/png")}
    data = {"prompt": "hello", "count": "1"}
    resp2 = client.post(
        "/api/external/marketing/collage",
        data=data,
        files=files,
        headers={"X-API-Key": key},
    )
    assert resp2.status_code == 201
    payload = resp2.json()
    assert payload["prompts"][0]["title"] == "t"

    # Missing/invalid key should be rejected
    resp3 = client.post(
        "/api/external/marketing/collage",
        data=data,
        files=files,
    )
    assert resp3.status_code == 401

