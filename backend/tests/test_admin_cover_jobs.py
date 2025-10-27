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


async def _seed(db_url: str) -> None:
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        session.add(
            models.CoverJob(
                request_id="req-cover-1",
                actor_type="admin",
                actor_id="admin",
                title="示例标题",
                subtitle=None,
                style_key="gradient",
                preset_id=None,
                status="succeeded",
                duration_ms=12.3,
            )
        )
        await session.commit()
    await engine.dispose()


def test_list_cover_jobs(tmp_path: Path) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "jobs.db")
    asyncio.run(_seed(db_url))

    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=db_url,
        auth_basic_username="admin",
        auth_basic_password_plain="secret",
    )

    with TestClient(app) as client:
        resp = client.get(
            "/api/admin/cover-jobs",
            headers={"Authorization": "Basic YWRtaW46c2VjcmV0"},
        )
        assert resp.status_code == 200
        items = resp.json()
        assert isinstance(items, list)
        assert any(j["request_id"] == "req-cover-1" for j in items)

    app.dependency_overrides.pop(get_settings, None)
