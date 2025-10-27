#!/usr/bin/env python3
"""Generate RED-style covers from a video file via CPU pipeline.

Usage:
  python backend/bin/make_red_cover.py \
    --video path/to/input.mp4 --title "示例标题" \
    [--subtitle "可选副标题"] [--style gradient|glass|sticker] \
    [--font /path/to/font.ttf] [--sticker 贴纸字样] [--outdir ./out]

Outputs two JPEGs: cover_1080x1920.jpg and cover_1080x1440.jpg in the outdir.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser(description="Generate RED-style covers from video")
    ap.add_argument("--video", required=True, help="Path to input video file")
    ap.add_argument("--title", required=True, help="Title text")
    ap.add_argument("--subtitle", default=None, help="Subtitle text")
    ap.add_argument(
        "--style",
        default="gradient",
        choices=["gradient", "glass", "sticker"],
        help="Cover style",
    )
    ap.add_argument("--font", default=None, help="Path to TTF/OTF font file")
    ap.add_argument("--sticker", default=None, help="Sticker text for sticker style")
    ap.add_argument("--outdir", default=".", help="Output directory")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    out_916 = outdir / "cover_1080x1920.jpg"
    out_34 = outdir / "cover_1080x1440.jpg"

    try:
        from app.services.covers import make_red_covers
    except Exception as exc:
        print("FATAL: missing media dependencies (Pillow/OpenCV):", exc)
        return 2

    try:
        _ = make_red_covers(
            args.video,
            title=args.title,
            subtitle=args.subtitle,
            font_path=args.font,
            export_9x16=str(out_916),
            export_3x4=str(out_34),
            style=args.style,  # type: ignore[arg-type]
            sticker=args.sticker,
        )
        print("Saved:")
        print(" -", out_916)
        print(" -", out_34)
        return 0
    except Exception as exc:  # pragma: no cover - CLI utility
        print("ERROR:", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

