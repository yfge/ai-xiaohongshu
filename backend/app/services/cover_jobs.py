"""Async cover job processor used by BackgroundTasks or Celery workers."""
from __future__ import annotations

import os
from sqlalchemy import select
import sqlalchemy as sa
from app.core.config import Settings
from app.db.session import get_session_maker
from app.db import models
from .covers import _load_pil  # ensure media deps reported early


async def process_cover_job(job_id: int, *, settings: Settings) -> None:
    """Process a cover job and update its DB status.

    Expects the job row to have `video_ref` set to a readable file path.
    Saves output JPEGs alongside the video file and updates result paths.
    """
    # Check deps; raise if missing
    try:
        _ = _load_pil()
        from .covers import make_red_covers  # noqa: F401
    except Exception as exc:  # pragma: no cover - environment specific
        session_maker = get_session_maker(settings)
        async with session_maker() as session:
            row = (
                await session.execute(select(models.CoverJob).where(models.CoverJob.id == job_id))
            ).scalar_one_or_none()
            if row:
                row.status = "failed"
                row.error = str(exc)
                await session.commit()
        return

    from .covers import make_red_covers
    import time as _t

    session_maker = get_session_maker(settings)
    async with session_maker() as session:
        row = (
            await session.execute(select(models.CoverJob).where(models.CoverJob.id == job_id))
        ).scalar_one_or_none()
        if not row or not row.video_ref:
            return
        row.status = "running"
        row.started_at = sa.func.now()  # type: ignore[attr-defined]
        row.progress_pct = 5.0
        await session.commit()
        started = _t.perf_counter()
        try:
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
            row.progress_pct = 100.0
        except Exception as exc:  # pragma: no cover - defensive
            row.attempts = int((row.attempts or 0) + 1)
            if row.attempts < int(row.max_attempts or 1):
                # Re-queue immediately for a simple retry strategy
                row.status = "queued"
                row.error = None
                await session.commit()
                # Schedule immediate retry by calling recursively
                await process_cover_job(job_id, settings=settings)
                return
            else:
                row.status = "failed"
                row.error = str(exc)
                row.progress_pct = None
        await session.commit()


__all__ = ["process_cover_job"]
