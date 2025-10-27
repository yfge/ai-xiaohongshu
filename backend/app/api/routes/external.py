"""External-facing API endpoints protected by API Key."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, UploadFile, status, Request

from app.core.config import Settings, get_settings
from app.api.routes.marketing import _to_uploaded_images
from app.deps import get_marketing_service
from app.schemas.marketing import MarketingGenerationResponse
from app.api.routes.creative import CoverResult, _generate_covers_impl
from app.security import require_api_key
from app.services.marketing import MarketingCollageService


router = APIRouter(prefix="/external", tags=["external"])


@router.post(
    "/marketing/collage",
    response_model=MarketingGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="对外：生成小红书营销组图",
)
async def external_generate_marketing_collage(
    _: object = Depends(require_api_key(["marketing:collage"])),
    prompt: str = Form(..., description="创意简报或初始提示词"),
    count: int = Form(..., ge=1, description="需要生成的提示词/图像数量"),
    images: List[UploadFile] = File(
        ..., description="1~M 张参考图片，将作为灵感输入"
    ),
    settings: Settings = Depends(get_settings),
    service: MarketingCollageService = Depends(get_marketing_service),
) -> MarketingGenerationResponse:
    uploaded_images = await _to_uploaded_images(images, settings=settings)
    return await service.generate_collage(brief=prompt, count=count, uploaded_images=uploaded_images)


@router.post(
    "/creative/covers",
    response_model=CoverResult,
    status_code=status.HTTP_201_CREATED,
    summary="对外：自动封面生成（9:16 与 3:4）",
)
async def external_generate_covers(
    _: object = Depends(require_api_key(["creative:covers"])),
    request: Request | None = None,
    title: str = Form(...),
    subtitle: str | None = Form(default=None),
    style: str = Form(default="gradient"),
    sticker: str | None = Form(default=None),
    preset_id: int | None = Form(default=None),
    preset_key: str | None = Form(default=None),
    video: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> CoverResult:
    # Reuse internal implementation to keep behavior consistent
    assert request is not None  # for type checkers
    return await _generate_covers_impl(
        request,
        title=title,
        subtitle=subtitle,
        style=style,
        sticker=sticker,
        preset_id=preset_id,
        preset_key=preset_key,
        video=video,
        settings=settings,
    )
