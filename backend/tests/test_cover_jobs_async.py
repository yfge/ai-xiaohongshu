from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

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


def test_enqueue_and_status(tmp_path: Path, monkeypatch) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "jobs.db")
    store = tmp_path / "covers"
    store.mkdir(parents=True, exist_ok=True)
    _prepare_db(db_url)

    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=db_url,
        covers_store_path=str(store),
    )

    # Bypass media deps and stub renderer to write dummy files
    from app.api.routes import creative as creative_mod  # type: ignore
    creative_mod._ensure_deps = lambda: None  # type: ignore

    def _fake_make_red_covers(video_path: str, **kwargs):  # type: ignore[no-redef]
        out1 = kwargs.get("export_9x16")
        out2 = kwargs.get("export_3x4")
        Path(out1).write_bytes(b"JPG1")  # type: ignore[arg-type]
        Path(out2).write_bytes(b"JPG2")  # type: ignore[arg-type]
    import types, sys
    fake_mod = types.SimpleNamespace(make_red_covers=_fake_make_red_covers)
    sys.modules["app.services.covers"] = fake_mod  # type: ignore

    # Enqueue job
    with TestClient(app) as client:
        files = {"video": ("v.mp4", b"00", "video/mp4")}
        data = {"title": "T", "style": "gradient"}
        r = client.post("/api/creative/cover-jobs", data=data, files=files)
        assert r.status_code == 200, r.text
        job_id = r.json()["id"]

    # Manually process (simulate worker)
    async def _process():
        from app.services.cover_jobs import process_cover_job
        await process_cover_job(job_id, settings=Settings(database_url=db_url))
    asyncio.run(_process())

    # Check status
    with TestClient(app) as client:
        r = client.get(f"/api/creative/cover-jobs/{job_id}")
        assert r.status_code == 200
        payload = r.json()
        assert payload["status"] == "succeeded"
        assert Path(payload["result_9x16_url"]).exists()
        assert Path(payload["result_3x4_url"]).exists()

    app.dependency_overrides.pop(get_settings, None)


def test_seed_cover_preset(tmp_path: Path, monkeypatch) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "seed.db")
    _prepare_db(db_url)

    import os
    os.environ["DATABASE_URL"] = db_url
    from backend.bin import seed_cover_preset as seed

    rc1 = asyncio.run(seed.main())
    rc2 = asyncio.run(seed.main())  # idempotent
    assert rc1 == 0
    assert rc2 == 0

    async def _count() -> int:
        engine = create_async_engine(db_url)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        async with session_maker() as session:
            rows = (await session.execute(models.CoverStylePreset.__table__.select())).fetchall()
        await engine.dispose()
        return len(rows)
    assert asyncio.run(_count()) >= 1

