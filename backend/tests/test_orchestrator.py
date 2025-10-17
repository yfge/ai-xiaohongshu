"""Tests for the agent orchestrator skeleton."""
from __future__ import annotations

import pytest

from app.services.agent_runs import AgentRunRecord
from app.services.orchestrator import AgentOrchestrator


class _RecorderStub:
    def __init__(self) -> None:
        self.records: list[AgentRunRecord] = []

    async def record(self, record: AgentRunRecord) -> None:
        self.records.append(record)


@pytest.mark.anyio
async def test_orchestrator_runs_steps_and_records() -> None:
    recorder = _RecorderStub()
    orchestrator = AgentOrchestrator(recorder=recorder)

    async def research_step(context: dict[str, object]) -> dict[str, object]:
        assert "initial" in context
        return {"prompts": [{"title": "insight"}]}

    async def planning_step(context: dict[str, object]) -> dict[str, object]:
        assert "ResearchAgent" in context
        return {"plan": "go-live"}

    orchestrator.register(agent_id="ResearchAgent", handler=research_step)
    orchestrator.register(agent_id="PlanningAgent", handler=planning_step)

    result = await orchestrator.run({"initial": True})

    assert result["ResearchAgent"]["prompts"][0]["title"] == "insight"
    assert result["PlanningAgent"]["plan"] == "go-live"

    assert len(recorder.records) == 2
    assert {record.agent_id for record in recorder.records} == {
        "ResearchAgent",
        "PlanningAgent",
    }
