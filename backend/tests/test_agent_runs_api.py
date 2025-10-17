"""Integration tests for agent run observability endpoints."""
from __future__ import annotations

from pathlib import Path

import asyncio
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.deps import get_agent_run_repository
from app.main import app
from app.services.agent_runs import AgentRunRecord, AgentRunRecorder, AgentRunRepository


@pytest.fixture(name="client")
def client_fixture(tmp_path: Path) -> TestClient:
    store_path = tmp_path / "runs.jsonl"
    recorder = AgentRunRecorder(store_path)
    app.dependency_overrides[get_settings] = lambda: Settings(
        ark_api_key="test",
        agent_run_store_path=str(store_path),
    )
    app.dependency_overrides[get_agent_run_repository] = lambda: AgentRunRepository(
        store_path
    )

    async def _seed() -> None:
        await recorder.record(
            AgentRunRecord(
                agent_id="CollageAgent",
                request_id="req-1",
                status="success",
                duration_ms=10,
                input_hash="hash-1",
                prompt_count=2,
                image_count=2,
            )
        )

    asyncio.run(_seed())

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.pop(get_settings, None)
    app.dependency_overrides.pop(get_agent_run_repository, None)


def test_list_agent_runs_returns_records(client: TestClient) -> None:
    response = client.get("/api/agent-runs")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total"] >= 1
    assert payload["runs"][0]["agent_id"] == "CollageAgent"
