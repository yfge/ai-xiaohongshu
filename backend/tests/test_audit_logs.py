"""Tests for audit log listing (JSONL and SQL modes)."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.main import app


def _basic_auth(username: str, password: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def test_audit_listing_jsonl(tmp_path: Path) -> None:
    audit_path = tmp_path / "audit.jsonl"
    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        audit_log_store_path=str(audit_path),
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
        database_url=None,
    )
    with TestClient(app) as client:
        # Trigger audit by calling /health
        resp = client.get("/health")
        assert resp.status_code == 200

        # List audit logs via admin endpoint
        resp2 = client.get("/api/admin/audit-logs", headers=_basic_auth("admin", "secret"))
        assert resp2.status_code == 200
        logs = resp2.json()
        assert isinstance(logs, list) and logs
        assert any(log.get("path") == "/health" for log in logs)
    app.dependency_overrides.pop(get_settings, None)


@pytest.mark.anyio
async def test_audit_listing_sql(tmp_path: Path) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "audit.db")
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()

    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        database_url=db_url,
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
    )
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        r2 = client.get("/api/admin/audit-logs", headers=_basic_auth("admin", "secret"))
        assert r2.status_code == 200
        logs = r2.json()
        assert logs and any(log.get("path") in {"/health", "/api/admin/audit-logs"} for log in logs)
    app.dependency_overrides.pop(get_settings, None)
