"""Utilities for recording agent execution metadata."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models


@dataclass(slots=True)
class AgentRunRecord:
    """Structured payload describing a single agent execution."""

    agent_id: str
    request_id: str
    status: str
    duration_ms: float
    input_hash: str
    prompt_count: int
    image_count: int
    error: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AgentRunRecorder:
    """Append agent run records to a JSONL file for later analysis."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def record(self, record: AgentRunRecord) -> None:
        """Persist a run record as a JSON line."""

        payload = json.dumps(asdict(record), ensure_ascii=False)
        async with self._lock:
            await asyncio.to_thread(self._append_line, payload)

    def _append_line(self, payload: str) -> None:
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(payload)
            handle.write("\n")


class AgentRunRepository:
    """Read agent runs from the JSONL store."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
    ) -> tuple[list[AgentRunRecord], int]:
        if limit <= 0:
            return [], 0

        records = await asyncio.to_thread(self._read_all)
        filtered = _apply_filters(records, agent_id=agent_id, status=status, since=since)

        total = len(filtered)
        start = min(offset, total)
        end = min(start + limit, total)
        return filtered[start:end], total

    def _read_all(self) -> list[AgentRunRecord]:
        if not self._path.exists():
            return []

        runs: list[AgentRunRecord] = []
        with self._path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    runs.append(_record_from_dict(payload))
                except json.JSONDecodeError:
                    continue
        runs.sort(key=lambda record: record.created_at, reverse=True)
        return runs


def _record_from_dict(payload: dict[str, Any]) -> AgentRunRecord:
    return AgentRunRecord(
        agent_id=payload.get("agent_id", "unknown"),
        request_id=payload.get("request_id", ""),
        status=payload.get("status", "unknown"),
        duration_ms=float(payload.get("duration_ms", 0.0)),
        input_hash=payload.get("input_hash", ""),
        prompt_count=int(payload.get("prompt_count", 0)),
        image_count=int(payload.get("image_count", 0)),
        error=payload.get("error"),
        metadata=payload.get("metadata", {}),
        created_at=payload.get("created_at", datetime.now(timezone.utc).isoformat()),
    )


def _apply_filters(
    records: Iterable[AgentRunRecord],
    *,
    agent_id: str | None,
    status: str | None,
    since: datetime | None,
) -> List[AgentRunRecord]:
    filtered: List[AgentRunRecord] = []
    for record in records:
        if agent_id and record.agent_id != agent_id:
            continue
        if status and record.status != status:
            continue
        if since:
            try:
                created = datetime.fromisoformat(record.created_at)
            except ValueError:
                continue
            if created < since:
                continue
        filtered.append(record)
    return filtered


class AgentRunSQLRecorder:
    """Persist agent runs into a SQL database."""

    def __init__(self, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker

    async def record(self, record: AgentRunRecord) -> None:
        created_at = _parse_created_at(record.created_at)
        async with self._session_maker() as session:
            session.add(
                models.AgentRun(
                    agent_id=record.agent_id,
                    request_id=record.request_id,
                    status=record.status,
                    duration_ms=record.duration_ms,
                    input_hash=record.input_hash,
                    prompt_count=record.prompt_count,
                    image_count=record.image_count,
                    error=record.error,
                    metadata_json=record.metadata or None,
                    created_at=created_at,
                )
            )
            await session.commit()


class AgentRunSQLRepository:
    """Query agent run history from SQL storage."""

    def __init__(self, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker

    async def list_runs(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        agent_id: str | None = None,
        status: str | None = None,
        since: datetime | None = None,
    ) -> tuple[list[AgentRunRecord], int]:
        if limit <= 0:
            return [], 0

        filters = []
        if agent_id:
            filters.append(models.AgentRun.agent_id == agent_id)
        if status:
            filters.append(models.AgentRun.status == status)
        if since:
            filters.append(models.AgentRun.created_at >= since)

        stmt: Select[models.AgentRun] = (
            select(models.AgentRun)
            .where(*filters)
            .order_by(models.AgentRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count(models.AgentRun.id)).where(*filters)

        async with self._session_maker() as session:
            rows = (await session.execute(stmt)).scalars().all()
            total = (await session.execute(count_stmt)).scalar_one()

        records = [_from_model(row) for row in rows]
        return records, int(total)


def _parse_created_at(value: str) -> datetime:
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.now(timezone.utc)


def _from_model(model: models.AgentRun) -> AgentRunRecord:
    created_at = model.created_at.isoformat() if model.created_at else datetime.now(timezone.utc).isoformat()
    return AgentRunRecord(
        agent_id=model.agent_id,
        request_id=model.request_id,
        status=model.status,
        duration_ms=model.duration_ms,
        input_hash=model.input_hash,
        prompt_count=model.prompt_count,
        image_count=model.image_count,
        error=model.error,
        metadata=model.metadata_json or {},
        created_at=created_at,
    )


__all__ = [
    "AgentRunRecorder",
    "AgentRunRepository",
    "AgentRunRecord",
    "AgentRunSQLRecorder",
    "AgentRunSQLRepository",
]
