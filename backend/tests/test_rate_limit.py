"""Tests for API key rate limiting middleware."""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.deps import get_marketing_service
from app.main import app
from app.schemas.marketing import GeneratedImage, MarketingGenerationResponse, PromptVariant


class _StubService:
    async def generate_collage(self, **_: object) -> MarketingGenerationResponse:  # type: ignore[override]
        pv = PromptVariant(title="t", prompt="p", description=None, hashtags=[])
        return MarketingGenerationResponse(prompts=[pv], images=[GeneratedImage(prompt=pv, image_url=None, image_base64="aGVsbG8=", size="512x512")])


def _basic_auth(username: str, password: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_rate_limit_per_api_key(tmp_path: Path) -> None:
    app.dependency_overrides[get_marketing_service] = lambda: _StubService()  # type: ignore[return-value]
    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        api_key_store_path=str(tmp_path / "keys.jsonl"),
        audit_log_store_path=str(tmp_path / "audit.jsonl"),
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
        api_key_rate_window_seconds=60,
        api_key_rate_max_requests=2,
    )
    with TestClient(app) as client:
        # issue a key
        r = client.post(
            "/api/admin/api-keys",
            json={"name": "rl", "scopes": ["marketing:collage"]},
            headers=_basic_auth("admin", "secret"),
        )
        assert r.status_code == 200
        key = r.json()["api_key"]

        # 1st request allowed
        files = {"images": ("a.png", b"12", "image/png")}
        data = {"prompt": "hi", "count": "1"}
        r1 = client.post("/api/external/marketing/collage", data=data, files=files, headers={"X-API-Key": key})
        assert r1.status_code == 201
        # 2nd allowed
        r2 = client.post("/api/external/marketing/collage", data=data, files=files, headers={"X-API-Key": key})
        assert r2.status_code == 201
        # 3rd should be 429
        r3 = client.post("/api/external/marketing/collage", data=data, files=files, headers={"X-API-Key": key})
        assert r3.status_code == 429

    app.dependency_overrides.pop(get_marketing_service, None)
    app.dependency_overrides.pop(get_settings, None)

