"""Utilities for recording agent execution metadata."""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


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
        self, *, limit: int = 50, offset: int = 0
    ) -> tuple[list[AgentRunRecord], int]:
        if limit <= 0:
            return [], 0

        records = await asyncio.to_thread(self._read_all)
        total = len(records)
        start = min(offset, total)
        end = min(start + limit, total)
        return records[start:end], total

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


__all__ = ["AgentRunRecorder", "AgentRunRepository", "AgentRunRecord"]
