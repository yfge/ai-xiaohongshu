"""Tests for agent run details (SQL-backed)."""
from __future__ import annotations

from pathlib import Path
import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import Settings, get_settings
from app.db.base import Base
from app.main import app
from app.schemas.marketing import GeneratedImage, PromptVariant
from app.services.agent_runs import (
    AgentRunRecord,
    AgentRunSQLRecorder,
    AgentRunSQLRepository,
)


pytestmark = pytest.mark.anyio("asyncio")


async def _seed_db(session_maker: async_sessionmaker) -> str:
    recorder = AgentRunSQLRecorder(session_maker)
    request_id = "req-details-1"
    record = AgentRunRecord(
        agent_id="CollageAgent",
        request_id=request_id,
        status="success",
        duration_ms=123.4,
        input_hash="hash-details-1",
        prompt_count=2,
        image_count=2,
        created_at="2024-07-03T00:00:00+00:00",
    )
    prompts = [
        PromptVariant(
            title="主题一",
            prompt="prompt-1",
            description="desc-1",
            hashtags=["tag1", "tag2"],
        ),
        PromptVariant(
            title="主题二",
            prompt="prompt-2",
            description=None,
            hashtags=[],
        ),
    ]
    images = [
        GeneratedImage(prompt=prompts[0], image_url="https://x/foo.png", image_base64=None, size="1024x1024"),
        GeneratedImage(prompt=prompts[1], image_url=None, image_base64="ZmFrZS1iNjQ=", size="512x512"),
    ]
    await recorder.record_details(record, prompts=prompts, images=images)
    return request_id


@pytest.mark.anyio
async def test_sql_repository_get_run_details(tmp_path: Path) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "details.db")
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    request_id = await _seed_db(session_maker)

    repo = AgentRunSQLRepository(session_maker)
    record, prompts, images = await repo.get_run_details(request_id)

    assert record.request_id == request_id
    assert len(prompts) == 2
    assert prompts[0].title == "主题一"
    assert len(images) == 2
    assert images[0].image_url and images[0].image_url.endswith("foo.png")

    await engine.dispose()


def test_agent_run_details_api_sql(tmp_path: Path) -> None:
    db_url = "sqlite+aiosqlite:///" + str(tmp_path / "api-details.db")

    async def prepare() -> str:
        engine = create_async_engine(db_url)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        session_maker = async_sessionmaker(engine, expire_on_commit=False)
        req_id = await _seed_db(session_maker)
        await engine.dispose()
        return req_id

    request_id = asyncio.run(prepare())

    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        database_url=db_url,
    )

    with TestClient(app) as client:
        resp = client.get(f"/api/agent-runs/{request_id}")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["run"]["request_id"] == request_id
        assert len(payload["prompts"]) == 2
        assert len(payload["images"]) == 2

    app.dependency_overrides.pop(get_settings, None)
