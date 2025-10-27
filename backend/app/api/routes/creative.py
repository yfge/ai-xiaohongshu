"""Creative endpoints: CPU-based RED cover generation.

Dependencies (optional): Pillow, OpenCV. If unavailable, the endpoint returns 503.
"""
from __future__ import annotations

import base64
import os
import tempfile
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.config import Settings
from app.db.session import get_session_maker
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy import select
from app.db import models


router = APIRouter(prefix="/creative", tags=["creative"])


class CoverImage(BaseModel):
    size: Literal["1080x1920", "1080x1440"]
    image_base64: str = Field(..., description="Base64-encoded JPEG content")


class CoverResult(BaseModel):
    request_id: str
    style: str
    title: str
    subtitle: str | None = None
    images: list[CoverImage]


class CoverJobEnqueueResult(BaseModel):
    id: int
    request_id: str
    status: str


class CoverJobStatus(BaseModel):
    id: int
    request_id: str
    status: str
    title: str
    subtitle: str | None = None
    style_key: str | None = None
    duration_ms: float | None = None
    result_9x16_url: str | None = None
    result_3x4_url: str | None = None
    error: str | None = None


def _ensure_deps():
    try:
        # Try importing inside to detect availability
        import cv2  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        raise HTTPException(status_code=503, detail="Cover generation dependencies not available")


async def _generate_covers_impl(
    request: Request,
    *,
    title: str,
    subtitle: str | None,
    style: str,
    sticker: str | None,
    preset_id: int | None,
    preset_key: str | None,
    video: UploadFile,
    settings: Settings,
) -> CoverResult:
    """Shared implementation for generating covers, used by internal and external endpoints."""
    _ensure_deps()

    import time as _t
    started = _t.perf_counter()
    actor = getattr(request.state, "actor", None) or {"type": "anonymous", "id": "-"}
    request_id = request.headers.get("x-request-id") or getattr(request.state, "request_id", None)
    if not request_id:
        import uuid

        request_id = uuid.uuid4().hex

    # Preset lookup (optional, only when DB configured)
    preset_row: models.CoverStylePreset | None = None
    font_path: str | None = getattr(settings, "cover_font_path", None)
    if settings.database_url and (preset_id or preset_key):
        session_maker: async_sessionmaker = get_session_maker(settings)
        async with session_maker() as session:
            if preset_id:
                preset_row = (
                    await session.execute(
                        select(models.CoverStylePreset).where(models.CoverStylePreset.id == preset_id)
                    )
                ).scalar_one_or_none()
            elif preset_key:
                preset_row = (
                    await session.execute(
                        select(models.CoverStylePreset).where(models.CoverStylePreset.key == preset_key)
                    )
                ).scalar_one_or_none()
            # Resolve font from preset if needed
            if preset_row and not font_path and preset_row.title_font_id:
                f = (
                    await session.execute(
                        select(models.Font).where(models.Font.id == preset_row.title_font_id)
                    )
                ).scalar_one_or_none()
                if f:
                    font_path = f.path

    # Apply preset values
    if preset_row:
        style = preset_row.style_type or style
        if not sticker and preset_row.sticker_default_text:
            sticker = preset_row.sticker_default_text

    try:
        with tempfile.TemporaryDirectory() as td:
            video_path = os.path.join(td, "input.mp4")
            raw = await video.read()
            with open(video_path, "wb") as f:
                f.write(raw)

            from app.services.covers import make_red_covers

            out_916 = os.path.join(td, "cover_1080x1920.jpg")
            out_34 = os.path.join(td, "cover_1080x1440.jpg")
            _ = make_red_covers(
                video_path,
                title=title,
                subtitle=subtitle,
                font_path=font_path,
                export_9x16=out_916,
                export_3x4=out_34,
                style=style,  # type: ignore[arg-type]
                sticker=sticker,
            )

            def _b64(path: str) -> str:
                with open(path, "rb") as rf:
                    return base64.b64encode(rf.read()).decode("ascii")

            elapsed_ms = (_t.perf_counter() - started) * 1000.0

            # Persist job (best-effort)
            if settings.database_url:
                try:
                    session_maker = get_session_maker(settings)
                    async with session_maker() as session:
                        session.add(
                            models.CoverJob(
                                request_id=request_id,
                                actor_type=str(actor.get("type")),
                                actor_id=str(actor.get("id")),
                                title=title,
                                subtitle=subtitle,
                                style_key=style,
                                preset_id=preset_row.id if preset_row else None,
                                status="succeeded",
                                duration_ms=elapsed_ms,
                                result_9x16_url=None,
                                result_3x4_url=None,
                            )
                        )
                        await session.commit()
                except Exception:
                    pass

            return CoverResult(
                request_id=request_id,
                style=style,
                title=title,
                subtitle=subtitle,
                images=[
                    CoverImage(size="1080x1920", image_base64=_b64(out_916)),
                    CoverImage(size="1080x1440", image_base64=_b64(out_34)),
                ],
            )
    except HTTPException:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        if settings.database_url:
            try:
                session_maker = get_session_maker(settings)
                async def _persist_fail():
                    async with session_maker() as session:
                        session.add(
                            models.CoverJob(
                                request_id=request_id,
                                actor_type=str(actor.get("type")),
                                actor_id=str(actor.get("id")),
                                title=title,
                                subtitle=subtitle,
                                style_key=style,
                                preset_id=preset_row.id if preset_row else None,
                                status="failed",
                                error=str(exc),
                            )
                        )
                        await session.commit()
                import asyncio as _asyncio
                _asyncio.get_event_loop().run_until_complete(_persist_fail())
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Cover generation failed: {exc}")


@router.post("/covers", response_model=CoverResult)
async def generate_covers(
    request: Request,
    title: str = Form(...),
    subtitle: str | None = Form(default=None),
    style: str = Form(default="gradient"),
    sticker: str | None = Form(default=None),
    preset_id: int | None = Form(default=None),
    preset_key: str | None = Form(default=None),
    video: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    """Generate RED-style covers (9:16 and 3:4) from a video file."""
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


async def _process_cover_job(
    job_id: int,
    *,
    settings: Settings,
) -> None:
    """Background task to process a cover job and update DB status.

    This skeleton uses local filesystem storage under covers_store_path.
    """
    # Ensure deps
    try:
        _ensure_deps()
    except HTTPException as exc:
        session_maker = get_session_maker(settings)
        async with session_maker() as session:
            row = (
                await session.execute(select(models.CoverJob).where(models.CoverJob.id == job_id))
            ).scalar_one_or_none()
            if row:
                row.status = "failed"
                row.error = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                await session.commit()
        return

    # Load job row and process
    session_maker = get_session_maker(settings)
    async with session_maker() as session:
        row = (
            await session.execute(select(models.CoverJob).where(models.CoverJob.id == job_id))
        ).scalar_one_or_none()
        if not row or not row.video_ref:
            return
        import time as _t
        started = _t.perf_counter()
        try:
            from app.services.covers import make_red_covers
            out_dir = os.path.dirname(row.video_ref)
            out_916 = os.path.join(out_dir, "cover_1080x1920.jpg")
            out_34 = os.path.join(out_dir, "cover_1080x1440.jpg")
            _ = make_red_covers(
                row.video_ref,
                title=row.title,
                subtitle=row.subtitle,
                export_9x16=out_916,
                export_3x4=out_34,
                style=(row.style_key or "gradient"),  # type: ignore[arg-type]
            )
            row.status = "succeeded"
            row.duration_ms = (_t.perf_counter() - started) * 1000.0
            row.result_9x16_url = out_916
            row.result_3x4_url = out_34
        except Exception as exc:  # pragma: no cover
            row.status = "failed"
            row.error = str(exc)
        await session.commit()


@router.post("/cover-jobs", response_model=CoverJobEnqueueResult, summary="异步入队封面生成任务")
async def enqueue_cover_job(
    background: BackgroundTasks,
    request: Request,
    title: str = Form(...),
    subtitle: str | None = Form(default=None),
    style: str = Form(default="gradient"),
    video: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
) -> CoverJobEnqueueResult:
    """Enqueue a background cover generation job.

    Stores the uploaded video in covers_store_path/<job_id>/input.mp4 and returns job id.
    """
    # Materialize upload into storage and create job row
    import uuid
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    session_maker: async_sessionmaker = get_session_maker(settings)
    async with session_maker() as session:
        job = models.CoverJob(
            request_id=request_id,
            actor_type=getattr(getattr(request, "state", {}), "actor", {}).get("type", "anonymous"),
            actor_id=getattr(getattr(request, "state", {}), "actor", {}).get("id", "-"),
            title=title,
            subtitle=subtitle,
            style_key=style,
            status="queued",
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)

        # Create storage dir and save video
        base = getattr(settings, "covers_store_path", "storage/covers")
        job_dir = os.path.join(base, str(job.id))
        os.makedirs(job_dir, exist_ok=True)
        video_path = os.path.join(job_dir, "input.mp4")
        raw = await video.read()
        with open(video_path, "wb") as f:
            f.write(raw)
        job.video_ref = video_path
        await session.commit()

    # Schedule background task
    background.add_task(_process_cover_job, job.id, settings=settings)

    return CoverJobEnqueueResult(id=job.id, request_id=request_id, status="queued")


@router.get("/cover-jobs/{job_id}", response_model=CoverJobStatus, summary="查询封面任务状态")
async def get_cover_job_status(
    job_id: int,
    settings: Settings = Depends(get_settings),
) -> CoverJobStatus:
    session_maker: async_sessionmaker = get_session_maker(settings)
    async with session_maker() as session:
        row = (
            await session.execute(select(models.CoverJob).where(models.CoverJob.id == job_id))
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="job not found")
        return CoverJobStatus(
            id=row.id,
            request_id=row.request_id,
            status=row.status,
            title=row.title,
            subtitle=row.subtitle,
            style_key=row.style_key,
            duration_ms=row.duration_ms,
            result_9x16_url=row.result_9x16_url,
            result_3x4_url=row.result_3x4_url,
            error=row.error,
        )
