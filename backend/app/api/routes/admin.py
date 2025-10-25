"""Admin endpoints for API key management (requires Basic auth)."""
from __future__ import annotations

from typing import List, Optional
from dataclasses import asdict

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.security import ApiKeyRecord, get_api_key_store, require_basic_user
from app.core.config import Settings, get_settings
from app.deps import get_audit_repository
from app.services.audit import AuditRepository


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
) -> ApiKeyCreateResponse:
    scopes = payload.scopes or ["marketing:collage"]
    rec, plaintext = store.issue_key(name=payload.name, scopes=scopes)
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
) -> list[ApiKeyListItem]:
    items: list[ApiKeyRecord] = store.list_keys()
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
) -> dict:
    updated = store.set_active(key_id, payload.is_active)
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


@router.get("/audit-logs", response_model=List[AuditLogItem], summary="列出审计日志")
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    actor_type: str | None = Query(None),
    since: str | None = Query(None, description="ISO 时间，返回此时间之后的记录"),
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
    logs = await repo.list_logs(limit=limit, actor_type=actor_type, since=since_dt)
    return [AuditLogItem(**asdict(log)) for log in logs]
