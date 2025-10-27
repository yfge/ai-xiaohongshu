from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
import asyncio
import types
import os

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db import models
from app.main import app


def _prepare_db(db_url: str) -> None:
    async def _go():
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()
    asyncio.run(_go())


def test_creative_covers_persists_job(tmp_path: Path, monkeypatch) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "covers_jobs.db")
    _prepare_db(db_url)

    # Override settings to use SQL
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=db_url,
    )

    # Stub out covers module before import in route handler
    # Also bypass dependency checks in the creative route
    fake_mod = types.SimpleNamespace()
    from app.api.routes import creative as creative_mod  # type: ignore
    creative_mod._ensure_deps = lambda: None  # type: ignore

    def _fake_make_red_covers(video_path: str, **kwargs):  # type: ignore[no-redef]
        # Write two small files to paths provided
        out1 = kwargs.get("export_9x16")
        out2 = kwargs.get("export_3x4")
        assert out1 and out2
        with open(out1, "wb") as f1:
            f1.write(b"JPEG9x16")
        with open(out2, "wb") as f2:
            f2.write(b"JPEG3x4")
        return None

    fake_mod.make_red_covers = _fake_make_red_covers
    sys.modules["app.services.covers"] = fake_mod  # type: ignore

    with TestClient(app) as client:
        files = {"video": ("v.mp4", b"00", "video/mp4")}
        data = {"title": "示例标题", "style": "gradient"}
        resp = client.post("/api/creative/covers", data=data, files=files)
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload["title"] == "示例标题"
        assert isinstance(payload["images"], list) and len(payload["images"]) == 2

    # Verify one job row exists
    async def _count_jobs() -> int:
        engine = create_async_engine(db_url)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            rows = (
                await session.execute(models.CoverJob.__table__.select())
            ).fetchall()
        await engine.dispose()
        return len(rows)

    count = asyncio.run(_count_jobs())
    assert count == 1

    app.dependency_overrides.pop(get_settings, None)
