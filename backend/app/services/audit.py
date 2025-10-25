"""Simple audit logger with JSONL storage.

Writes one JSON line per request with actor, path, method and status code.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


@dataclass(slots=True)
class AuditRecord:
    actor_type: str
    actor_id: str
    request_id: str
    method: str
    path: str
    status_code: int
    ip: str | None = None
    user_agent: str | None = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def log(self, record: AuditRecord) -> None:
        payload = json.dumps(asdict(record), ensure_ascii=False)
        async with self._lock:
            await asyncio.to_thread(self._append_line, payload)

    def _append_line(self, payload: str) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")


# SQL-backed logger and repositories
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db import models


class AuditSQLLogger:
    def __init__(self, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker

    async def log(self, record: AuditRecord) -> None:  # type: ignore[override]
        async with self._session_maker() as session:
            session.add(
                models.AuditLog(
                    actor_type=record.actor_type,
                    actor_id=record.actor_id,
                    request_id=record.request_id,
                    method=record.method,
                    path=record.path,
                    status_code=record.status_code,
                    ip=record.ip,
                    user_agent=record.user_agent,
                    duration_ms=record.metadata.get("duration_ms"),
                    req_bytes=record.metadata.get("req_bytes"),
                    res_bytes=record.metadata.get("res_bytes"),
                    metadata_json=record.metadata or None,
                )
            )
            await session.commit()


class AuditRepository:
    async def list_logs(
        self,
        *,
        limit: int = 50,
        actor_type: str | None = None,
        since: datetime | None = None,
        method: str | None = None,
        status_code: int | None = None,
        path_prefix: str | None = None,
        request_id: str | None = None,
        offset: int = 0,
    ) -> list[AuditRecord]:
        raise NotImplementedError


class FileAuditRepository(AuditRepository):
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    async def list_logs(
        self,
        *,
        limit: int = 50,
        actor_type: str | None = None,
        since: datetime | None = None,
        method: str | None = None,
        status_code: int | None = None,
        path_prefix: str | None = None,
        request_id: str | None = None,
        offset: int = 0,
    ) -> list[AuditRecord]:
        lines: list[AuditRecord] = []
        if not self._path.exists():
            return []
        # Read entire file; acceptable for small dev logs
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    rec = AuditRecord(
                        actor_type=obj.get("actor_type", "unknown"),
                        actor_id=obj.get("actor_id", "-"),
                        request_id=obj.get("request_id", "-"),
                        method=obj.get("method", "GET"),
                        path=obj.get("path", "/"),
                        status_code=int(obj.get("status_code", 0)),
                        ip=obj.get("ip"),
                        user_agent=obj.get("user_agent"),
                        metadata=obj.get("metadata", {}),
                        created_at=obj.get("created_at", datetime.now(timezone.utc).isoformat()),
                    )
                    lines.append(rec)
                except Exception:
                    continue
        # Filter and tail by created_at descending
        lines.sort(key=lambda r: r.created_at, reverse=True)
        if actor_type:
            lines = [r for r in lines if r.actor_type == actor_type]
        if since:
            lines = [r for r in lines if _parse_datetime(r.created_at) >= since]
        if method:
            lines = [r for r in lines if r.method == method]
        if status_code is not None:
            lines = [r for r in lines if r.status_code == status_code]
        if path_prefix:
            lines = [r for r in lines if r.path.startswith(path_prefix)]
        if request_id:
            lines = [r for r in lines if r.request_id == request_id]
        start = max(0, offset)
        end = start + max(1, min(limit, 200))
        return lines[start:end]


class SQLAuditRepository(AuditRepository):
    def __init__(self, session_maker: async_sessionmaker) -> None:
        self._session_maker = session_maker

    async def list_logs(
        self,
        *,
        limit: int = 50,
        actor_type: str | None = None,
        since: datetime | None = None,
        method: str | None = None,
        status_code: int | None = None,
        path_prefix: str | None = None,
        request_id: str | None = None,
        offset: int = 0,
    ) -> list[AuditRecord]:
        filters = []
        if actor_type:
            filters.append(models.AuditLog.actor_type == actor_type)
        if since:
            filters.append(models.AuditLog.created_at >= since)
        if method:
            filters.append(models.AuditLog.method == method)
        if status_code is not None:
            filters.append(models.AuditLog.status_code == status_code)
        if path_prefix:
            filters.append(models.AuditLog.path.like(f"{path_prefix}%"))
        if request_id:
            filters.append(models.AuditLog.request_id == request_id)
        stmt: Select[models.AuditLog] = (
            select(models.AuditLog)
            .where(*filters)
            .order_by(models.AuditLog.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        async with self._session_maker() as session:
            rows = (await session.execute(stmt)).scalars().all()
        results: list[AuditRecord] = []
        for row in rows:
            results.append(
                AuditRecord(
                    actor_type=row.actor_type,
                    actor_id=row.actor_id,
                    request_id=row.request_id,
                    method=row.method,
                    path=row.path,
                    status_code=row.status_code,
                    ip=row.ip,
                    user_agent=row.user_agent,
                    metadata={
                        "duration_ms": row.duration_ms,
                        "req_bytes": row.req_bytes,
                        "res_bytes": row.res_bytes,
                    },
                    created_at=row.created_at.isoformat(),
                )
            )
        return results


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.now(timezone.utc)
