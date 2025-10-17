"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Depends

from functools import lru_cache

from app.core.config import Settings, get_settings
from app.services.agent_runs import AgentRunRecorder, AgentRunRepository
from app.services.marketing import MarketingCollageService


@lru_cache
def _create_agent_run_recorder(path: str) -> AgentRunRecorder:
    return AgentRunRecorder(path)


def get_agent_run_recorder(
    settings: Settings = Depends(get_settings),
) -> AgentRunRecorder:
    """Return a shared AgentRunRecorder instance."""

    return _create_agent_run_recorder(settings.agent_run_store_path)


def get_agent_run_repository(
    settings: Settings = Depends(get_settings),
) -> AgentRunRepository:
    """Return a repository for reading agent run records."""

    return AgentRunRepository(settings.agent_run_store_path)


def get_marketing_service(
    settings: Settings = Depends(get_settings),
    recorder: AgentRunRecorder = Depends(get_agent_run_recorder),
) -> MarketingCollageService:
    """Provide a marketing collage service instance per request."""

    return MarketingCollageService(settings, recorder=recorder)
