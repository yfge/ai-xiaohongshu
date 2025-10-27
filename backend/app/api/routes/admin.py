"""Admin endpoints for API key management (requires Basic auth)."""
from __future__ import annotations

from typing import List, Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel, Field

from app.security import ApiKeyRecord, get_api_key_store, require_basic_user
from app.core.config import Settings, get_settings
from app.deps import get_audit_repository
from app.services.audit import AuditRepository
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker
from app.db.session import get_session_maker
from app.db import models


router = APIRouter(prefix="/admin", tags=["admin"])


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., description="API Key 名称")
    scopes: Optional[List[str]] = Field(default=None, description="授权的 scope 列表")


class ApiKeyCreateResponse(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    created_at: str
    api_key: str = Field(..., description="明文 API Key，仅创建时返回")


@router.post("/api-keys", response_model=ApiKeyCreateResponse, summary="创建 API Key")
async def create_api_key(
    payload: ApiKeyCreateRequest,
    _: dict = Depends(require_basic_user),
    store=Depends(get_api_key_store),
    settings: Settings = Depends(get_settings),
) -> ApiKeyCreateResponse:
    scopes = payload.scopes or ["marketing:collage"]
    try:
        issued = store.issue_key(name=payload.name, scopes=scopes)
        if hasattr(issued, "__await__"):
            rec, plaintext = await issued  # type: ignore[misc]
        else:
            rec, plaintext = issued  # type: ignore[assignment]
    except Exception:
        # Fallback to file store if SQL not ready
        from app.security import ApiKeyStore as _FileStore

        fs = _FileStore(settings.api_key_store_path)
        rec, plaintext = fs.issue_key(name=payload.name, scopes=scopes)
    return ApiKeyCreateResponse(
        id=rec.id,
        name=rec.name,
        prefix=rec.prefix,
        scopes=scopes,
        is_active=rec.is_active,
        created_at=rec.created_at,
        api_key=plaintext,
    )


class ApiKeyListItem(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: List[str]
    is_active: bool
    created_at: str
    last_used_at: str | None = None


@router.get("/api-keys", response_model=List[ApiKeyListItem], summary="列出 API Key")
async def list_api_keys(
    _: dict = Depends(require_basic_user),
    store=Depends(get_api_key_store),
    settings: Settings = Depends(get_settings),
) -> list[ApiKeyListItem]:
    try:
        items_maybe = store.list_keys()
        if hasattr(items_maybe, "__await__"):
            items: list[ApiKeyRecord] = await items_maybe  # type: ignore[assignment]
        else:
            items = items_maybe  # type: ignore[assignment]
    except Exception:
        from app.security import ApiKeyStore as _FileStore

        fs = _FileStore(settings.api_key_store_path)
        items = fs.list_keys()
    return [
        ApiKeyListItem(
            id=i.id,
            name=i.name,
            prefix=i.prefix,
            scopes=i.scopes,
            is_active=i.is_active,
            created_at=i.created_at,
            last_used_at=i.last_used_at,
        )
        for i in items
    ]


class ApiKeyUpdateRequest(BaseModel):
    is_active: bool = Field(..., description="是否启用该 API Key")


@router.patch("/api-keys/{key_id}", summary="启用/禁用 API Key")
async def update_api_key(
    key_id: str,
    payload: ApiKeyUpdateRequest,
    _: dict = Depends(require_basic_user),
    store=Depends(get_api_key_store),
    settings: Settings = Depends(get_settings),
) -> dict:
    try:
        maybe = store.set_active(key_id, payload.is_active)
        if hasattr(maybe, "__await__"):
            updated = await maybe  # type: ignore[assignment]
        else:
            updated = maybe  # type: ignore[assignment]
    except Exception:
        from app.security import ApiKeyStore as _FileStore

        fs = _FileStore(settings.api_key_store_path)
        updated = fs.set_active(key_id, payload.is_active)
    return {"updated": bool(updated)}


class AuditLogItem(BaseModel):
    actor_type: str
    actor_id: str
    request_id: str
    method: str
    path: str
    status_code: int
    ip: str | None = None
    user_agent: str | None = None
    created_at: str
    duration_ms: float | None = None
    req_bytes: int | None = None
    res_bytes: int | None = None


@router.get("/audit-logs", response_model=List[AuditLogItem], summary="列出审计日志")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    actor_type: str | None = Query(None),
    since: str | None = Query(None, description="ISO 时间，返回此时间之后的记录"),
    method: str | None = Query(None),
    status_code: int | None = Query(None),
    path_prefix: str | None = Query(None),
    request_id: str | None = Query(None),
    _: dict = Depends(require_basic_user),
    settings: Settings = Depends(get_settings),
) -> list[AuditLogItem]:
    repo: AuditRepository = get_audit_repository(settings)
    from datetime import datetime

    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except Exception:
            since_dt = None
    logs = await repo.list_logs(
        limit=limit,
        actor_type=actor_type,
        since=since_dt,
        method=method,
        status_code=status_code,
        path_prefix=path_prefix,
        request_id=request_id,
        offset=offset,
    )
    items: list[AuditLogItem] = []
    for log in logs:
        base = asdict(log)
        meta = (log.metadata or {})
        base["duration_ms"] = meta.get("duration_ms")
        base["req_bytes"] = meta.get("req_bytes")
        base["res_bytes"] = meta.get("res_bytes")
        base.pop("metadata", None)
        items.append(AuditLogItem(**base))
    return items


# ---- Cover presets CRUD ----


class CoverPresetCreateRequest(BaseModel):
    key: str = Field(..., description="唯一 key")
    name: str = Field(..., description="名称")
    style_type: str = Field(..., description="glass|gradient|sticker")
    title_font_id: int | None = Field(default=None)
    subtitle_font_id: int | None = Field(default=None)
    safe_margin_pct: float | None = Field(default=None)
    padding_pct: float | None = Field(default=None)
    palette_start: str | None = Field(default=None)
    palette_end: str | None = Field(default=None)
    shadow: bool | None = Field(default=None)
    sticker_default_text: str | None = Field(default=None)
    params: dict | None = Field(default=None)


class CoverPresetUpdateRequest(BaseModel):
    name: str | None = None
    style_type: str | None = None
    title_font_id: int | None = None
    subtitle_font_id: int | None = None
    safe_margin_pct: float | None = None
    padding_pct: float | None = None
    palette_start: str | None = None
    palette_end: str | None = None
    shadow: bool | None = None
    sticker_default_text: str | None = None
    params: dict | None = None


class CoverPresetItem(BaseModel):
    id: int
    key: str
    name: str
    style_type: str
    title_font_id: int | None = None
    subtitle_font_id: int | None = None
    safe_margin_pct: float | None = None
    padding_pct: float | None = None
    palette_start: str | None = None
    palette_end: str | None = None
    shadow: bool | None = None
    sticker_default_text: str | None = None
    params: dict | None = None
    created_at: str


@router.post("/cover-presets", response_model=CoverPresetItem, summary="创建样式预设")
async def create_cover_preset(
    payload: CoverPresetCreateRequest,
    _: dict = Depends(require_basic_user),
    settings: Settings = Depends(get_settings),
):
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="数据库未配置")
    session_maker: async_sessionmaker = get_session_maker(settings)
    async with session_maker() as session:
        row = models.CoverStylePreset(
            key=payload.key,
            name=payload.name,
            style_type=payload.style_type,
            title_font_id=payload.title_font_id,
            subtitle_font_id=payload.subtitle_font_id,
            safe_margin_pct=payload.safe_margin_pct,
            padding_pct=payload.padding_pct,
            palette_start=payload.palette_start,
            palette_end=payload.palette_end,
            shadow=payload.shadow,
            sticker_default_text=payload.sticker_default_text,
            params=payload.params,
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail="key 已存在")
        await session.refresh(row)
        return CoverPresetItem(
            id=row.id,
            key=row.key,
            name=row.name,
            style_type=row.style_type,
            title_font_id=row.title_font_id,
            subtitle_font_id=row.subtitle_font_id,
            safe_margin_pct=row.safe_margin_pct,
            padding_pct=row.padding_pct,
            palette_start=row.palette_start,
            palette_end=row.palette_end,
            shadow=row.shadow,
            sticker_default_text=row.sticker_default_text,
            params=row.params or None,
            created_at=row.created_at.isoformat(),
        )


@router.get("/cover-presets", response_model=list[CoverPresetItem], summary="列出样式预设")
async def list_cover_presets(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: dict = Depends(require_basic_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverPresetItem]:
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="数据库未配置")
    session_maker: async_sessionmaker = get_session_maker(settings)
    stmt = (
        select(models.CoverStylePreset)
        .order_by(models.CoverStylePreset.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    async with session_maker() as session:
        rows = (await session.execute(stmt)).scalars().all()
    return [
        CoverPresetItem(
            id=r.id,
            key=r.key,
            name=r.name,
            style_type=r.style_type,
            title_font_id=r.title_font_id,
            subtitle_font_id=r.subtitle_font_id,
            safe_margin_pct=r.safe_margin_pct,
            padding_pct=r.padding_pct,
            palette_start=r.palette_start,
            palette_end=r.palette_end,
            shadow=r.shadow,
            sticker_default_text=r.sticker_default_text,
            params=r.params or None,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.patch("/cover-presets/{preset_id}", summary="更新样式预设")
async def update_cover_preset(
    preset_id: int,
    payload: CoverPresetUpdateRequest,
    _: dict = Depends(require_basic_user),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="数据库未配置")
    session_maker: async_sessionmaker = get_session_maker(settings)
    values = {k: v for k, v in payload.dict().items() if v is not None}
    if not values:
        return {"updated": False}
    stmt = (
        update(models.CoverStylePreset)
        .where(models.CoverStylePreset.id == preset_id)
        .values(**values)
    )
    async with session_maker() as session:
        res = await session.execute(stmt)
        await session.commit()
        updated = res.rowcount if hasattr(res, "rowcount") else None
    return {"updated": bool(updated)}


# ---- Cover jobs list ----


class CoverJobItem(BaseModel):
    id: int
    request_id: str
    actor_type: str
    actor_id: str
    title: str
    subtitle: str | None = None
    style_key: str | None = None
    preset_id: int | None = None
    status: str
    duration_ms: float | None = None
    result_9x16_url: str | None = None
    result_3x4_url: str | None = None
    created_at: str


@router.get("/cover-jobs", response_model=list[CoverJobItem], summary="列出封面生成任务")
async def list_cover_jobs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    status: str | None = Query(None),
    _: dict = Depends(require_basic_user),
    settings: Settings = Depends(get_settings),
) -> list[CoverJobItem]:
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="数据库未配置")
    session_maker: async_sessionmaker = get_session_maker(settings)
    filters = []
    if status:
        filters.append(models.CoverJob.status == status)
    stmt = (
        select(models.CoverJob)
        .where(*filters)
        .order_by(models.CoverJob.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    async with session_maker() as session:
        rows = (await session.execute(stmt)).scalars().all()
    return [
        CoverJobItem(
            id=r.id,
            request_id=r.request_id,
            actor_type=r.actor_type,
            actor_id=r.actor_id,
            title=r.title,
            subtitle=r.subtitle,
            style_key=r.style_key,
            preset_id=r.preset_id,
            status=r.status,
            duration_ms=r.duration_ms,
            result_9x16_url=r.result_9x16_url,
            result_3x4_url=r.result_3x4_url,
            created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]
