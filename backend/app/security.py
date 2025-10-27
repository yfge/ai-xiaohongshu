"""Lightweight security utilities: Basic auth and API key validation.

No external crypto deps; uses PBKDF2-HMAC for password hashing and HMAC-SHA256
for API key hashing/verification.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.core.config import Settings, get_settings
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.session import get_session_maker
from app.db import models


# ---------------------
# Basic auth (admin)
# ---------------------

_basic = HTTPBasic(auto_error=False)


def _pbkdf2(password: str, *, salt: bytes, rounds: int = 200_000) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
    return f"pbkdf2_sha256${rounds}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_pbkdf2(password: str, encoded: str) -> bool:
    try:
        algo, rounds_s, salt_b64, hash_b64 = encoded.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        rounds = int(rounds_s)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def _derive_hash_from_settings(settings: Settings) -> Optional[str]:
    if settings.auth_basic_password_hash:
        return settings.auth_basic_password_hash
    if settings.auth_basic_password_plain:
        # derive with a static salt per process; sufficient for basic dev use
        salt = hashlib.sha256(b"ai-xiaohongshu-basic-salt").digest()[:16]
        return _pbkdf2(settings.auth_basic_password_plain, salt=salt)
    return None


async def require_basic_user(
    request: Request,
    settings: Settings = Depends(get_settings),
    credentials: HTTPBasicCredentials | None = Depends(_basic),
) -> dict:
    """Validate HTTP Basic credentials against configured admin user.

    Sets request.state.actor for audit middleware.
    """
    if not credentials or not settings.auth_basic_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要管理员认证")

    username = credentials.username or ""
    password = credentials.password or ""
    if username != settings.auth_basic_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")

    encoded = _derive_hash_from_settings(settings)
    if not encoded or not _verify_pbkdf2(password, encoded):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="认证失败")

    # Mark actor for audit middleware
    request.state.actor = {"type": "user", "id": username}
    return {"username": username, "roles": ["admin"]}


# ---------------------
# API keys (JSONL store)
# ---------------------


@dataclass(slots=True)
class ApiKeyRecord:
    id: str
    name: str
    prefix: str
    hashed_key: str
    scopes: list[str]
    is_active: bool
    created_at: str
    last_used_at: str | None = None


class ApiKeyStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _append_line(self, payload: str) -> None:
        with self._path.open("a", encoding="utf-8") as fh:
            fh.write(payload)
            fh.write("\n")

    def _read_all(self) -> list[ApiKeyRecord]:
        if not self._path.exists():
            return []
        items: list[ApiKeyRecord] = []
        with self._path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    items.append(
                        ApiKeyRecord(
                            id=obj["id"],
                            name=obj["name"],
                            prefix=obj["prefix"],
                            hashed_key=obj["hashed_key"],
                            scopes=list(obj.get("scopes", [])),
                            is_active=bool(obj.get("is_active", True)),
                            created_at=obj.get("created_at", datetime.now(timezone.utc).isoformat()),
                            last_used_at=obj.get("last_used_at"),
                        )
                    )
                except Exception:
                    continue
        return items

    def _write_all(self, items: list[ApiKeyRecord]) -> None:
        tmp = self._path.with_suffix(".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            for item in items:
                fh.write(json.dumps(asdict(item), ensure_ascii=False))
                fh.write("\n")
        tmp.replace(self._path)

    def issue_key(self, *, name: str, scopes: Iterable[str]) -> tuple[ApiKeyRecord, str]:
        prefix = os.urandom(6).hex()
        secret = os.urandom(24).hex()
        plaintext = f"{prefix}.{secret}"
        hashed = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        rec = ApiKeyRecord(
            id=os.urandom(8).hex(),
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            scopes=list(scopes),
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        items = self._read_all()
        items.append(rec)
        self._write_all(items)
        return rec, plaintext

    def verify_key(self, plaintext: str) -> ApiKeyRecord | None:
        try:
            prefix, _ = plaintext.split(".", 1)
        except ValueError:
            return None
        hashed = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        for item in self._read_all():
            if item.prefix == prefix and hmac.compare_digest(item.hashed_key, hashed) and item.is_active:
                return item
        return None

    def touch_last_used(self, rec: ApiKeyRecord) -> None:
        items = self._read_all()
        for i, item in enumerate(items):
            if item.id == rec.id:
                items[i].last_used_at = datetime.now(timezone.utc).isoformat()
                break
        self._write_all(items)

    def list_keys(self) -> list[ApiKeyRecord]:
        return self._read_all()

    def set_active(self, key_id: str, active: bool) -> bool:
        items = self._read_all()
        changed = False
        for i, item in enumerate(items):
            if item.id == key_id:
                items[i].is_active = active
                changed = True
        if changed:
            self._write_all(items)
        return changed


import json  # after annotations


def get_api_key_store(settings: Settings = Depends(get_settings)) -> ApiKeyStore | "SQLApiKeyStore":
    """Dependency returning appropriate API key store per settings.

    - If DATABASE_URL is set, returns SQL-backed store (async methods)
    - Otherwise returns file-backed JSONL store (sync methods)
    """
    if getattr(settings, "database_url", None):
        session_maker = get_session_maker(settings)
        return SQLApiKeyStore(session_maker)
    return ApiKeyStore(settings.api_key_store_path)


def require_api_key(scopes: Iterable[str]) -> Callable:
    async def _dep(
        request: Request,
        store: ApiKeyStore | SQLApiKeyStore = Depends(get_api_key_store),
        settings: Settings = Depends(get_settings),
    ) -> ApiKeyRecord:
        header = request.headers.get("X-API-Key")
        if not header:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少 API Key")
        # Support both sync and async store implementations; fallback to file store on SQL error
        try:
            rec = store.verify_key(header)
            if hasattr(rec, "__await__"):
                rec = await rec  # type: ignore[assignment]
        except Exception:
            rec = None
        if not rec:
            try:
                fs = ApiKeyStore(settings.api_key_store_path)
                rec = fs.verify_key(header)
            except Exception:
                rec = None
        if not rec:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API Key 无效")
        # scope check
        need = set(scopes)
        if need and not need.issubset(set(rec.scopes)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="权限不足")
        try:
            touch = store.touch_last_used(rec)
            if hasattr(touch, "__await__"):
                await touch  # type: ignore[misc]
        except Exception:
            pass
        request.state.actor = {"type": "api_key", "id": rec.id}
        return rec

    return _dep


class SQLApiKeyStore(ApiKeyStore):  # pragma: no cover - exercised via API tests
    """SQL-backed API key store with async methods.

    Methods mirror the file-backed store but are async. Callers should detect
    coroutine return values and await accordingly (see require_api_key and admin routes).
    """

    def __init__(self, session_maker: async_sessionmaker):  # type: ignore[override]
        self._session_maker = session_maker

    async def issue_key(self, *, name: str, scopes: Iterable[str]) -> tuple[ApiKeyRecord, str]:  # type: ignore[override]
        prefix = os.urandom(6).hex()
        secret = os.urandom(24).hex()
        plaintext = f"{prefix}.{secret}"
        hashed = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        rec = ApiKeyRecord(
            id=os.urandom(8).hex(),
            name=name,
            prefix=prefix,
            hashed_key=hashed,
            scopes=list(scopes),
            is_active=True,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        scopes_json = {"scopes": rec.scopes} if rec.scopes else None
        async with self._session_maker() as session:
            session.add(
                models.ApiKey(
                    id=rec.id,
                    name=rec.name,
                    prefix=rec.prefix,
                    hashed_key=rec.hashed_key,
                    scopes=scopes_json,
                    is_active=True,
                )
            )
            await session.commit()
        return rec, plaintext

    async def list_keys(self) -> list[ApiKeyRecord]:  # type: ignore[override]
        async with self._session_maker() as session:
            rows = (await session.execute(select(models.ApiKey))).scalars().all()
        items: list[ApiKeyRecord] = []
        for row in rows:
            scopes = []
            if row.scopes and isinstance(row.scopes, dict):
                maybe = row.scopes.get("scopes")
                if isinstance(maybe, list):
                    scopes = [str(s) for s in maybe]
            items.append(
                ApiKeyRecord(
                    id=row.id,
                    name=row.name,
                    prefix=row.prefix,
                    hashed_key=row.hashed_key,
                    scopes=scopes,
                    is_active=row.is_active,
                    created_at=row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat(),
                    last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
                )
            )
        return items

    async def verify_key(self, plaintext: str) -> ApiKeyRecord | None:  # type: ignore[override]
        try:
            prefix, _ = plaintext.split(".", 1)
        except ValueError:
            return None
        hashed = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
        async with self._session_maker() as session:
            row = (
                await session.execute(
                    select(models.ApiKey).where(
                        models.ApiKey.prefix == prefix,
                        models.ApiKey.hashed_key == hashed,
                        models.ApiKey.is_active == True,  # noqa: E712
                    )
                )
            ).scalar_one_or_none()
            if not row:
                return None
            scopes = []
            if row.scopes and isinstance(row.scopes, dict):
                maybe = row.scopes.get("scopes")
                if isinstance(maybe, list):
                    scopes = [str(s) for s in maybe]
            return ApiKeyRecord(
                id=row.id,
                name=row.name,
                prefix=row.prefix,
                hashed_key=row.hashed_key,
                scopes=scopes,
                is_active=row.is_active,
                created_at=row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat(),
                last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
            )

    async def set_active(self, key_id: str, active: bool) -> bool:  # type: ignore[override]
        async with self._session_maker() as session:
            row = (
                await session.execute(select(models.ApiKey).where(models.ApiKey.id == key_id))
            ).scalar_one_or_none()
            if not row:
                return False
            row.is_active = bool(active)
            await session.commit()
            return True

    async def touch_last_used(self, rec: ApiKeyRecord) -> None:  # type: ignore[override]
        async with self._session_maker() as session:
            row = (
                await session.execute(select(models.ApiKey).where(models.ApiKey.id == rec.id))
            ).scalar_one_or_none()
            if not row:
                return None
            row.last_used_at = datetime.now(timezone.utc)
            await session.commit()
            return None

    def touch_last_used(self, rec: ApiKeyRecord) -> None:  # type: ignore[override]
        async def _update() -> None:
            async with self._session_maker() as session:
                await session.execute(
                    update(models.ApiKey)
                    .where(models.ApiKey.id == rec.id)
                    .values(last_used_at=datetime.now(timezone.utc))
                )
                await session.commit()
        import asyncio as _asyncio
        _asyncio.get_event_loop().run_until_complete(_update())

    def list_keys(self) -> list[ApiKeyRecord]:  # type: ignore[override]
        async def _list() -> list[ApiKeyRecord]:
            async with self._session_maker() as session:
                rows = (await session.execute(select(models.ApiKey))).scalars().all()
            items: list[ApiKeyRecord] = []
            for row in rows:
                scopes: list[str] = []
                if row.scopes and isinstance(row.scopes, dict):
                    maybe = row.scopes.get("scopes")
                    if isinstance(maybe, list):
                        scopes = [str(s) for s in maybe]
                items.append(
                    ApiKeyRecord(
                        id=row.id,
                        name=row.name,
                        prefix=row.prefix,
                        hashed_key=row.hashed_key,
                        scopes=scopes,
                        is_active=row.is_active,
                        created_at=row.created_at.isoformat() if row.created_at else datetime.now(timezone.utc).isoformat(),
                        last_used_at=row.last_used_at.isoformat() if row.last_used_at else None,
                    )
                )
            return items

        import asyncio as _asyncio
        return _asyncio.get_event_loop().run_until_complete(_list())

    def set_active(self, key_id: str, active: bool) -> bool:  # type: ignore[override]
        async def _toggle() -> int:
            async with self._session_maker() as session:
                res = await session.execute(
                    update(models.ApiKey).where(models.ApiKey.id == key_id).values(is_active=active)
                )
                await session.commit()
                return res.rowcount or 0
        import asyncio as _asyncio
        return (_asyncio.get_event_loop().run_until_complete(_toggle())) > 0
