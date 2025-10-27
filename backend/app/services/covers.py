"""CPU-based RED cover generator (frame picking + text rendering).

The implementation avoids importing heavy dependencies at module import time to keep
the rest of the app fast and test-friendly. We import Pillow and OpenCV lazily inside
functions and fall back to PIL's default font when configured fonts are unavailable.

Functions:
- pick_cover_frame(video_path): select a representative frame for cover rendering.
- make_red_covers(...): render 9:16 and 3:4 covers with styles: glass/gradient/sticker.

Note: This module is self-contained and does not perform any I/O outside of the
provided paths. The API layer is responsible for writing temporary files and returning
results to clients.
"""
from __future__ import annotations

from typing import Any, Literal, Tuple


StyleKey = Literal["glass", "gradient", "sticker"]


def _load_cv2():  # pragma: no cover - import guard
    try:
        import cv2  # type: ignore

        return cv2
    except Exception as exc:  # pragma: no cover - best effort
        raise RuntimeError("OpenCV (cv2) is required for cover generation") from exc


def _load_pil():  # pragma: no cover - import guard
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter  # type: ignore

        return Image, ImageDraw, ImageFont, ImageFilter
    except Exception as exc:  # pragma: no cover - best effort
        raise RuntimeError("Pillow (PIL) is required for cover generation") from exc


def _load_font(ImageFont, path: str | None, size: int):
    try:
        if path:
            return ImageFont.truetype(path, size)
    except Exception:
        pass
    # Fallback to default font (may not fully support CJK, but prevents crashes)
    try:
        return ImageFont.load_default()
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("Failed to load any font for cover generation") from exc


def pick_cover_frame(video_path: str, fps_sample: float = 1.0, max_frames: int = 300):
    """Pick a good cover frame by scoring sampled frames.

    Heuristics: brightness gate, sharpness (Laplacian variance), entropy,
    subtitle penalty (bottom edge density), face bonus.
    """
    cv2 = _load_cv2()
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise RuntimeError("Cannot open video")
    rate = cap.get(cv2.CAP_PROP_FPS) or 25
    step = max(1, int(rate / fps_sample))
    best: Tuple[float, Any | None] = (-1e9, None)
    idx, kept = 0, 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if idx % step != 0:
            idx += 1
            continue

        small = (
            cv2.resize(
                frame,
                (720, int(frame.shape[0] * 720 / frame.shape[1])),
                interpolation=cv2.INTER_AREA,
            )
            if frame.shape[1] > 720
            else frame
        )
        score = score_frame_for_red(small, face_cascade)
        if score > best[0]:
            best = (score, frame)

        kept += 1
        if kept >= max_frames:
            break
        idx += 1
    cap.release()
    if best[1] is None:
        raise RuntimeError("No suitable frame found")
    return best[1]


def score_frame_for_red(bgr, face_cascade) -> float:
    import numpy as np  # lazy but light
    cv2 = _load_cv2()
    h, w = bgr.shape[:2]
    # brightness
    y = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV)[:, :, 0]
    bright = float(y.mean())
    if bright < 32 or bright > 235:
        return -1e9
    # sharpness
    lap = cv2.Laplacian(cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
    # entropy
    hist = cv2.calcHist([y], [0], None, [64], [0, 256])
    p = (hist / hist.sum() + 1e-8).ravel()
    entropy = float(-(p * np.log2(p)).sum())
    # subtitle penalty (bottom 18%)
    bottom = bgr[int(h * 0.82) :, :]
    edges = cv2.Canny(cv2.cvtColor(bottom, cv2.COLOR_BGR2GRAY), 80, 160)
    subtitle_penalty = edges.mean() / 255 * 0.9

    # face bonus
    faces = face_cascade.detectMultiScale(
        cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY), 1.1, 5, minSize=(int(w * 0.08), int(w * 0.08))
    )
    face_bonus = 0.0
    if len(faces) > 0:
        area = max([fw * fh for (_, _, fw, fh) in faces]) / (w * h)
        face_bonus = min(1.0, area * 6.0) * 2.0
    return (lap / 220.0) + (entropy / 5.0) - subtitle_penalty + face_bonus


def _wrap_text(draw, text: str, font, max_w: int) -> str:
    lines, line = [], ""
    for ch in text:
        test = line + ch
        w = draw.textbbox((0, 0), test, font=font)[2]
        if w <= max_w:
            line = test
        else:
            if line:
                lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return "\n".join(lines)


def _draw_text_with_outline(draw, xy, text, font, fill=(255, 255, 255, 255), stroke=2):
    draw.multiline_text(
        xy,
        text,
        font=font,
        fill=fill,
        spacing=int(font.size * 0.25) if getattr(font, "size", None) else 4,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255),
    )


def _style_glass_banner(img, title, subtitle, font_path):
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()
    W, H = img.size
    im = img.convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    title_font = _load_font(ImageFont, font_path, int(H * 0.075))
    sub_font = _load_font(ImageFont, font_path, int(H * 0.045))
    max_w = int(W * 0.88)
    title_wrapped = _wrap_text(draw, title, title_font, max_w)
    sub_wrapped = _wrap_text(draw, subtitle, sub_font, max_w) if subtitle else ""

    tb = draw.multiline_textbbox(
        (0, 0), title_wrapped, font=title_font, spacing=int(getattr(title_font, "size", 40) * 0.25)
    )
    sb = (
        draw.multiline_textbbox(
            (0, 0), sub_wrapped, font=sub_font, spacing=int(getattr(sub_font, "size", 24) * 0.25)
        )
        if subtitle
        else (0, 0, 0, 0)
    )
    text_w = max(tb[2] - tb[0], sb[2] - sb[0])
    text_h = (tb[3] - tb[1]) + (sb[3] - sb[1] if subtitle else 0) + int(H * 0.02)

    pad = int(W * 0.025)
    band_w, band_h = text_w + pad * 2, text_h + pad * 2
    x = (W - band_w) // 2
    y = int(H * 0.06)  # top
    radius = int(getattr(title_font, "size", 40) * 0.5)

    overlay = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(overlay, "RGBA")
    sd.rounded_rectangle([x, y + 2, x + band_w, y + band_h + 2], radius=radius, fill=(0, 0, 0, 150))
    overlay = overlay.filter(ImageFilter.GaussianBlur(3))
    im = Image.alpha_composite(im, overlay)

    plate = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 140))
    pd = ImageDraw.Draw(plate, "RGBA")
    pd.rounded_rectangle([0, 0, band_w, band_h], radius=radius, fill=(0, 0, 0, 140))
    im.alpha_composite(plate, (x, y))

    draw = ImageDraw.Draw(im, "RGBA")
    ty = y + pad
    _draw_text_with_outline(draw, (x + pad, ty), title_wrapped, title_font, stroke=2)
    if subtitle:
        ty += (tb[3] - tb[1]) + int(H * 0.012)
        _draw_text_with_outline(draw, (x + pad, ty), sub_wrapped, sub_font, stroke=2)

    return im.convert("RGB")


def _style_gradient_ribbon(img, title, subtitle, font_path):
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()  # noqa: F401
    W, H = img.size
    im = img.convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    title_font = _load_font(ImageFont, font_path, int(H * 0.085))
    sub_font = _load_font(ImageFont, font_path, int(H * 0.048))
    max_w = int(W * 0.92)
    title_wrapped = _wrap_text(draw, title, title_font, max_w)
    sub_wrapped = _wrap_text(draw, subtitle, sub_font, max_w) if subtitle else ""

    band_h = int(H * 0.24)
    band = Image.new("RGBA", (W, band_h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(band, "RGBA")
    # linear gradient: #FF2442 → #FF7A45
    for i in range(W):
        t = i / (W - 1)
        r = int((1 - t) * 0xFF + t * 0xFF)
        g = int((1 - t) * 0x24 + t * 0x7A)
        b = int((1 - t) * 0x42 + t * 0x45)
        bd.line([(i, 0), (i, band_h)], fill=(r, g, b, 205))
    mask = Image.new("L", (W, band_h), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [int(W * 0.04), int(H * 0.03), W - int(W * 0.04), band_h - int(H * 0.01)],
        radius=int(H * 0.04),
        fill=255,
    )
    im.alpha_composite(band, (0, int(H * 0.05)), mask)

    draw = ImageDraw.Draw(im, "RGBA")
    tx = int(W * 0.08)
    ty = int(H * 0.08)
    _draw_text_with_outline(draw, (tx, ty), title_wrapped, title_font, stroke=2)
    if subtitle:
        tb = draw.multiline_textbbox((0, 0), title_wrapped, font=title_font)
        ty += (tb[3] - tb[1]) + int(H * 0.008)
        _draw_text_with_outline(draw, (tx, ty), sub_wrapped, sub_font, stroke=2)
    return im.convert("RGB")


def _style_sticker_corner(img, title, subtitle, font_path, sticker_text: str = "保姆级"):
    Image, ImageDraw, ImageFont, ImageFilter = _load_pil()  # noqa: F401
    W, H = img.size
    im = img.convert("RGBA")
    draw = ImageDraw.Draw(im, "RGBA")

    sticker_w = int(W * 0.32)
    sticker_h = int(W * 0.13)
    sticker = Image.new("RGBA", (sticker_w, sticker_h), (255, 255, 255, 0))
    sd = ImageDraw.Draw(sticker, "RGBA")
    sd.rounded_rectangle(
        [0, 0, sticker_w, sticker_h], radius=int(sticker_h * 0.5), fill=(255, 36, 66, 235)
    )
    sfont = _load_font(ImageFont, font_path, int(sticker_h * 0.52))
    sw = sd.textbbox((0, 0), sticker_text, font=sfont)[2]
    sd.text(((sticker_w - sw) // 2, int(sticker_h * 0.18)), sticker_text, font=sfont, fill=(255, 255, 255, 255))
    im.alpha_composite(sticker, (int(W * 0.06), int(H * 0.06)))

    title_font = _load_font(ImageFont, font_path, int(H * 0.078))
    sub_font = _load_font(ImageFont, font_path, int(H * 0.045))
    max_w = int(W * 0.9)
    title_wrapped = _wrap_text(draw, title, title_font, max_w)
    sub_wrapped = _wrap_text(draw, subtitle, sub_font, max_w) if subtitle else ""

    tb = draw.multiline_textbbox(
        (0, 0), title_wrapped, font=title_font, spacing=int(getattr(title_font, "size", 36) * 0.25)
    )
    sb = (
        draw.multiline_textbbox(
            (0, 0), sub_wrapped, font=sub_font, spacing=int(getattr(sub_font, "size", 24) * 0.25)
        )
        if subtitle
        else (0, 0, 0, 0)
    )
    text_w = max(tb[2] - tb[0], sb[2] - sb[0])
    text_h = (tb[3] - tb[1]) + (sb[3] - sb[1] if subtitle else 0) + int(H * 0.02)
    pad = int(W * 0.025)
    band_w, band_h = text_w + pad * 2, text_h + pad * 2
    x = (W - band_w) // 2
    y = int(H * 0.64)

    plate = Image.new("RGBA", im.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(plate, "RGBA")
    radius = int(getattr(title_font, "size", 36) * 0.45)
    pd.rounded_rectangle([x, y, x + band_w, y + band_h], radius=radius, fill=(0, 0, 0, 150))
    plate = plate.filter(ImageFilter.GaussianBlur(3))
    im = Image.alpha_composite(im, plate)

    plate2 = Image.new("RGBA", (band_w, band_h), (0, 0, 0, 140))
    p2d = ImageDraw.Draw(plate2, "RGBA")
    p2d.rounded_rectangle([0, 0, band_w, band_h], radius=radius, fill=(0, 0, 0, 140))
    im.alpha_composite(plate2, (x, y))

    draw = ImageDraw.Draw(im, "RGBA")
    ty = y + pad
    _draw_text_with_outline(draw, (x + pad, ty), title_wrapped, title_font, stroke=2)
    if subtitle:
        ty += (tb[3] - tb[1]) + int(H * 0.01)
        _draw_text_with_outline(draw, (x + pad, ty), sub_wrapped, sub_font, stroke=2)
    return im.convert("RGB")


def render_cover_styles(
    pil_img,  # PIL.Image.Image
    title: str,
    subtitle: str | None = None,
    font_path: str | None = None,
    size: tuple[int, int] = (1080, 1920),
    style: StyleKey = "gradient",
    sticker_text: str | None = None,
):
    Image, *_ = _load_pil()
    base = pil_img.convert("RGB").resize(size, Image.LANCZOS)
    if style == "glass":
        return _style_glass_banner(base, title, subtitle, font_path)
    if style == "gradient":
        return _style_gradient_ribbon(base, title, subtitle, font_path)
    if style == "sticker":
        return _style_sticker_corner(base, title, subtitle, font_path, sticker_text or "保姆级")
    raise ValueError("unknown style")


def make_red_covers(
    video_path: str,
    title: str,
    subtitle: str | None = None,
    font_path: str | None = None,
    export_9x16: str | None = "cover_1080x1920.jpg",
    export_3x4: str | None = "cover_1080x1440.jpg",
    style: StyleKey = "gradient",
    sticker: str | None = None,
):
    """Run the full pipeline and save to given paths (if provided).

    Returns a tuple of two PIL images (9:16, 3:4) for further processing or
    serialization by the API layer.
    """
    cv2 = _load_cv2()
    Image, *_ = _load_pil()

    frame = pick_cover_frame(video_path)
    pil = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))

    c1 = render_cover_styles(
        pil, title, subtitle, font_path, size=(1080, 1920), style=style, sticker_text=sticker
    )
    if export_9x16:
        try:
            c1.save(export_9x16, quality=95)
        except Exception:
            pass

    W, H = pil.size
    target_ratio = 3 / 4
    if W / H > target_ratio:
        new_w = int(H * target_ratio)
        x0 = (W - new_w) // 2
        pil_34 = pil.crop((x0, 0, x0 + new_w, H))
    else:
        new_h = int(W / target_ratio)
        y0 = (H - new_h) // 2
        pil_34 = pil.crop((0, y0, W, y0 + new_h))
    c2 = render_cover_styles(
        pil_34, title, subtitle, font_path, size=(1080, 1440), style=style, sticker_text=sticker
    )
    if export_3x4:
        try:
            c2.save(export_3x4, quality=95)
        except Exception:
            pass

    return c1, c2

