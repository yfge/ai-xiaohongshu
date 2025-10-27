#!/usr/bin/env python3
"""Seed a sample cover style preset for quick UI validation.

Reads DATABASE_URL from backend/.env or environment. Idempotent.
"""
from __future__ import annotations

import os
from pathlib import Path
import asyncio


async def main() -> int:
    # Load .env if present
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL not set; cannot seed preset")
        return 2

    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import select
    from app.db import models
    from app.db.base import Base

    engine = create_async_engine(url, future=True)
    async with engine.begin() as conn:
        # Ensure tables exist (in case migrations were not run)
        await conn.run_sync(Base.metadata.create_all)
        res = await conn.execute(select(models.CoverStylePreset).where(models.CoverStylePreset.key == "gradient_red"))
        row = res.scalar_one_or_none()
        if row:
            print("Preset already exists: gradient_red")
            return 0
        await conn.execute(
            models.CoverStylePreset.__table__.insert().values(
                key="gradient_red",
                name="Red Gradient",
                style_type="gradient",
                safe_margin_pct=0.06,
                padding_pct=0.04,
                palette_start="#FF2442",
                palette_end="#FF7A45",
                shadow=True,
            )
        )
    await engine.dispose()
    print("Seeded preset: gradient_red")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

