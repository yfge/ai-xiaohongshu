"""Marketing workflow endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.deps import get_marketing_service
from app.schemas.marketing import MarketingGenerationResponse
from app.services.marketing import (
    ArkConfigurationError,
    ArkServiceError,
    MarketingCollageService,
    UploadedImage,
)

router = APIRouter(prefix="/marketing", tags=["marketing"])


@router.post(
    "/collage",
    response_model=MarketingGenerationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="生成小红书营销组图",
)
async def generate_marketing_collage(
    prompt: str = Form(..., description="创意简报或初始提示词"),
    count: int = Form(..., ge=1, description="需要生成的提示词/图像数量"),
    images: List[UploadFile] = File(
        ..., description="1~M 张参考图片，将作为灵感输入"
    ),
    service: MarketingCollageService = Depends(get_marketing_service),
) -> MarketingGenerationResponse:
    """Return prompt variants and generated images for Xiaohongshu marketing."""

    uploaded_images = await _to_uploaded_images(images)

    try:
        return await service.generate_collage(
            brief=prompt,
            count=count,
            uploaded_images=uploaded_images,
        )
    except ArkConfigurationError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except ArkServiceError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _to_uploaded_images(files: List[UploadFile]) -> List[UploadedImage]:
    uploads: List[UploadedImage] = []
    for file in files:
        data = await file.read()
        if not data:
            continue
        uploads.append(
            UploadedImage(
                filename=file.filename or "uploaded-image",
                content_type=file.content_type,
                data=data,
            )
        )
    return uploads
