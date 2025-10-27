"""Celery integration (optional).

If REDIS_URL is configured and Celery is installed, this module exposes a Celery
app and a helper `enqueue_cover_job_celery` to submit jobs. Otherwise it no-ops.
"""
from __future__ import annotations

import os
from typing import Any

from app.core.config import get_settings
from app.services.cover_jobs import process_cover_job

_CELERY = None


def _get_celery() -> Any | None:
    global _CELERY
    if _CELERY is not None:
        return _CELERY
    redis_url = os.environ.get("REDIS_URL") or getattr(get_settings(), "redis_url", None)
    if not redis_url:
        _CELERY = None
        return None
    try:
        from celery import Celery  # type: ignore
    except Exception:
        _CELERY = None
        return None
    app = Celery("ai_xhs", broker=redis_url, backend=redis_url)

    @app.task(name="covers.process_job")
    def _process(job_id: int) -> str:  # type: ignore[no-redef]
        import asyncio as _asyncio
        # Use current settings on worker
        settings = get_settings()
        _asyncio.run(process_cover_job(int(job_id), settings=settings))
        return "ok"

    _CELERY = app
    return _CELERY


def enqueue_cover_job_celery(job_id: int) -> bool:
    app = _get_celery()
    if not app:
        return False
    try:
        app.send_task("covers.process_job", args=[int(job_id)])
        return True
    except Exception:
        return False


__all__ = ["enqueue_cover_job_celery"]

