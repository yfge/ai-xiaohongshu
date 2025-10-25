"""Auth endpoints using HTTP Basic for minimal admin access."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.security import require_basic_user


router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", summary="获取当前用户信息（Basic）")
async def get_me(user: dict = Depends(require_basic_user)) -> dict:
    return user

