"""Agent run observability endpoints."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.deps import get_agent_run_repository
from app.schemas.agent_runs import AgentRun, AgentRunListResponse
from app.services.agent_runs import AgentRunRepository


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


@router.get(
    "",
    response_model=AgentRunListResponse,
    summary="列出 Agent 执行记录",
)
async def list_agent_runs(
    limit: int = Query(50, ge=1, le=200, description="单次返回的记录数"),
    offset: int = Query(0, ge=0, description="分页偏移量"),
    agent_id: str | None = Query(None, description="按 Agent ID 过滤"),
    status: str | None = Query(None, description="按执行状态过滤"),
    since: datetime | None = Query(None, description="仅返回此时间之后的记录"),
    repository: AgentRunRepository = Depends(get_agent_run_repository),
) -> AgentRunListResponse:
    """Return paginated agent run records for observability dashboards."""

    runs, total = await repository.list_runs(
        limit=limit,
        offset=offset,
        agent_id=agent_id,
        status=status,
        since=since,
    )
    return AgentRunListResponse(
        runs=[AgentRun.model_validate(asdict(run)) for run in runs],
        total=total,
        limit=limit,
        offset=offset,
    )
