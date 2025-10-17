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


__all__ = ["AgentRunRecorder", "AgentRunRecord"]
