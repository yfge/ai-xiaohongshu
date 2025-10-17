"""Tests for reading agent run records."""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.services.agent_runs import AgentRunRecord, AgentRunRecorder, AgentRunRepository


@pytest.mark.anyio
async def test_repository_lists_runs(tmp_path: Path) -> None:
    store_path = tmp_path / "runs.jsonl"
    recorder = AgentRunRecorder(store_path)
    await recorder.record(
        AgentRunRecord(
            agent_id="CollageAgent",
            request_id="req-1",
            status="success",
            duration_ms=12.5,
            input_hash="hash-1",
            prompt_count=2,
            image_count=2,
        )
    )
    await recorder.record(
        AgentRunRecord(
            agent_id="ResearchAgent",
            request_id="req-2",
            status="failed",
            duration_ms=20.5,
            input_hash="hash-2",
            prompt_count=0,
            image_count=0,
            error="boom",
        )
    )

    repository = AgentRunRepository(store_path)
    runs, total = await repository.list_runs(limit=10)

    assert total == 2
    assert len(runs) == 2
    assert runs[0].request_id == "req-2"
    assert runs[1].request_id == "req-1"


@pytest.mark.anyio
async def test_repository_handles_missing_file(tmp_path: Path) -> None:
    repository = AgentRunRepository(tmp_path / "missing.jsonl")
    runs, total = await repository.list_runs()
    assert runs == []
    assert total == 0
