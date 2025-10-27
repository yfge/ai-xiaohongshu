from __future__ import annotations

from pathlib import Path

import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db import models
from app.main import app


pytestmark = pytest.mark.anyio("asyncio")


def _basic_auth(username: str, password: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


async def _prepare(db_url: str) -> None:
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def test_cover_preset_crud(tmp_path: Path) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "presets.db")
    asyncio.run(_prepare(db_url))

    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=db_url,
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
    )

    with TestClient(app) as client:
        # Create
        resp = client.post(
            "/api/admin/cover-presets",
            json={
                "key": "gradient-red",
                "name": "红橙渐变",
                "style_type": "gradient",
                "palette_start": "#FF2442",
                "palette_end": "#FF7A45",
                "sticker_default_text": "保姆级",
            },
            headers=_basic_auth("admin", "secret"),
        )
        assert resp.status_code == 200, resp.text
        item = resp.json()
        assert item["key"] == "gradient-red"

        # Duplicate key should 409
        resp_dup = client.post(
            "/api/admin/cover-presets",
            json={
                "key": "gradient-red",
                "name": "重复",
                "style_type": "gradient",
            },
            headers=_basic_auth("admin", "secret"),
        )
        assert resp_dup.status_code == 409

        # List
        resp2 = client.get(
            "/api/admin/cover-presets",
            headers=_basic_auth("admin", "secret"),
        )
        assert resp2.status_code == 200
        items = resp2.json()
        assert any(p["key"] == "gradient-red" for p in items)

        # Update
        preset_id = item["id"]
        resp3 = client.patch(
            f"/api/admin/cover-presets/{preset_id}",
            json={"name": "红橙渐变（改）", "sticker_default_text": "避坑"},
            headers=_basic_auth("admin", "secret"),
        )
        assert resp3.status_code == 200
        assert resp3.json().get("updated") is True

    app.dependency_overrides.pop(get_settings, None)

