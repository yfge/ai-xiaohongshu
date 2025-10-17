"""Marketing workflow endpoints."""
from __future__ import annotations

import mimetypes
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import Settings, get_settings
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
    settings: Settings = Depends(get_settings),
    service: MarketingCollageService = Depends(get_marketing_service),
) -> MarketingGenerationResponse:
    """Return prompt variants and generated images for Xiaohongshu marketing."""

    uploaded_images = await _to_uploaded_images(images, settings=settings)

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


UPLOAD_READ_CHUNK_SIZE = 64 * 1024  # 64 KiB per chunk


async def _to_uploaded_images(
    files: List[UploadFile], *, settings: Settings
) -> List[UploadedImage]:
    uploads: List[UploadedImage] = []
    for file in files:
        content_type = _resolve_content_type(file)
        if content_type and not any(
            content_type.startswith(prefix)
            for prefix in settings.collage_allowed_mime_prefixes
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文件 {file.filename or 'uploaded-image'} 不是支持的图片格式",
            )

        data = await _read_upload_bytes(file, limit=settings.collage_upload_max_bytes)
        if not data:
            continue
        uploads.append(
            UploadedImage(
                filename=file.filename or "uploaded-image",
                content_type=file.content_type,
                data=data,
            )
        )
    if not uploads:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一张有效的图片",
        )
    return uploads


def _resolve_content_type(file: UploadFile) -> str | None:
    if file.content_type:
        return file.content_type
    guessed_type, _ = mimetypes.guess_type(file.filename or "")
    return guessed_type


async def _read_upload_bytes(file: UploadFile, *, limit: int) -> bytes:
    total = 0
    chunks: list[bytes] = []
    try:
        while True:
            remaining = limit - total
            if remaining <= 0:
                raise _payload_too_large(limit)

            chunk = await file.read(min(UPLOAD_READ_CHUNK_SIZE, remaining))
            if not chunk:
                break

            total += len(chunk)
            if total > limit:
                raise _payload_too_large(limit)
            chunks.append(chunk)
    finally:
        await file.close()

    return b"".join(chunks)


def _payload_too_large(limit: int) -> HTTPException:
    size_mb = limit / (1024 * 1024)
    if size_mb.is_integer():
        size_label = f"{int(size_mb)}MB"
    else:
        size_label = f"{size_mb:.1f}MB"
    return HTTPException(
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        detail=f"单张图片大小不能超过 {size_label}",
    )
