"""FastAPI dependency helpers."""
from __future__ import annotations

from fastapi import Depends

from functools import lru_cache
from typing import Union

from app.core.config import Settings, get_settings
from app.db.session import get_session_maker
from app.services.agent_runs import (
    AgentRunRecorder,
    AgentRunRepository,
    AgentRunSQLRecorder,
    AgentRunSQLRepository,
)
from app.services.marketing import MarketingCollageService


@lru_cache
def _create_agent_run_recorder(path: str) -> AgentRunRecorder:
    return AgentRunRecorder(path)


def get_agent_run_recorder(
    settings: Settings = Depends(get_settings),
) -> Union[AgentRunRecorder, AgentRunSQLRecorder]:
    """Return a shared AgentRunRecorder instance."""

    if settings.database_url:
        session_maker = get_session_maker(settings)
        return AgentRunSQLRecorder(session_maker)
    return _create_agent_run_recorder(settings.agent_run_store_path)


def get_agent_run_repository(
    settings: Settings = Depends(get_settings),
) -> Union[AgentRunRepository, AgentRunSQLRepository]:
    """Return a repository for reading agent run records."""

    if settings.database_url:
        session_maker = get_session_maker(settings)
        return AgentRunSQLRepository(session_maker)
    return AgentRunRepository(settings.agent_run_store_path)


def get_marketing_service(
    settings: Settings = Depends(get_settings),
    recorder: AgentRunRecorder = Depends(get_agent_run_recorder),
) -> MarketingCollageService:
    """Provide a marketing collage service instance per request."""

    return MarketingCollageService(settings, recorder=recorder)
