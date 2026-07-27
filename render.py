"""Thumbnail rendering engine.

Produces 1280x720 YouTube thumbnails in a fixed "editorial panel" template:
a solid color panel on one side holding a large all-caps serif title and a
letter-spaced subtitle, with the source photo filling the other side.

This module is pure rendering logic (no GUI) so it can be scripted and tested.
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field, replace

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Constants matched to the reference thumbnail
# ---------------------------------------------------------------------------

CANVAS_W = 1280
CANVAS_H = 720

DEFAULT_PANEL_COLOR = "#72204E"   # sampled from the reference
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_PANEL_FRAC = 0.488        # panel width as a fraction of the canvas
DEFAULT_SUBTITLE = "20 MINUTE PRACTICE"


def _resource_dir() -> str:
    """Directory that holds bundled data (fonts).

    When frozen by PyInstaller, data files are unpacked to sys._MEIPASS
    (onefile) or sit beside the executable (onedir). Otherwise it's the
    directory of this source file.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


FONT_PATH = os.path.join(_resource_dir(), "fonts", "PlayfairDisplay-VF.ttf")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class Style:
    """All the knobs the GUI exposes. Sensible defaults reproduce the reference."""

    panel_color: str = DEFAULT_PANEL_COLOR
    text_color: str = DEFAULT_TEXT_COLOR
    panel_frac: float = DEFAULT_PANEL_FRAC
    panel_side: str = "left"          # "left" or "right"
    subtitle: str = DEFAULT_SUBTITLE
    title_weight: str = "Regular"     # Playfair variation name
    subtitle_weight: str = "Medium"
    uppercase: bool = True
    subtitle_tracking: float = 0.18   # extra letter-spacing as a fraction of font size


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def title_from_filename(path: str) -> str:
    """Derive a display title from a file name: 'feet-first.jpg' -> 'FEET FIRST'."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for sep in ("_", "-", "."):
        stem = stem.replace(sep, " ")
    return " ".join(stem.split()).strip()


def _load_font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(FONT_PATH, size)
    try:
        font.set_variation_by_name(weight)
    except Exception:
        pass
    return font


def _wrap_title(words: list[str]) -> list[str]:
    """Split a title into up to two visually balanced lines.

    One or two words -> one word per line. More words -> balance by length.
    """
    if len(words) <= 1:
        return words or [""]
    if len(words) == 2:
        return [words[0], words[1]]
    # Balance: find the split minimising the difference in character length.
    best_i, best_diff = 1, None
    for i in range(1, len(words)):
        a = len(" ".join(words[:i]))
        b = len(" ".join(words[i:]))
        diff = abs(a - b)
        if best_diff is None or diff < best_diff:
            best_i, best_diff = i, diff
    return [" ".join(words[:best_i]), " ".join(words[best_i:])]


def _fit_font(draw, lines, weight, max_w, start_size, min_size=24):
    """Largest font size at which every line fits within max_w."""
    size = start_size
    while size > min_size:
        font = _load_font(weight, size)
        widest = max((draw.textlength(ln, font=font) for ln in lines), default=0)
        if widest <= max_w:
            return font, size
        size -= 4
    return _load_font(weight, min_size), min_size


def _draw_tracked(draw, xy, text, font, fill, tracking_px):
    """Draw text with manual per-character letter spacing (tracking)."""
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking_px


def _tracked_width(draw, text, font, tracking_px):
    if not text:
        return 0
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking_px * (len(text) - 1)


# ---------------------------------------------------------------------------
# Core render
# ---------------------------------------------------------------------------

def render_thumbnail(photo_path: str, title: str, style: Style) -> Image.Image:
    """Render a single 1280x720 thumbnail and return it as a PIL Image."""
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), style.panel_color)
    draw = ImageDraw.Draw(canvas)

    panel_w = int(round(CANVAS_W * style.panel_frac))
    photo_w = CANVAS_W - panel_w
    panel_on_left = style.panel_side == "left"
    photo_x0 = panel_w if panel_on_left else 0
    panel_x0 = 0 if panel_on_left else photo_w

    # --- photo: cover-crop into the photo region ---
    with Image.open(photo_path) as src:
        photo = src.convert("RGB")
    photo = _cover_crop(photo, photo_w, CANVAS_H)
    canvas.paste(photo, (photo_x0, 0))

    # --- panel background (repaint in case photo overlapped due to rounding) ---
    draw.rectangle([panel_x0, 0, panel_x0 + panel_w, CANVAS_H], fill=style.panel_color)

    # --- title ---
    display_title = title.upper() if style.uppercase else title
    words = display_title.split()
    lines = _wrap_title(words)

    margin = int(panel_w * 0.09)
    text_max_w = panel_w - 2 * margin

    title_font, title_size = _fit_font(
        draw, lines, style.title_weight, text_max_w, start_size=int(panel_w * 0.30)
    )
    line_gap = int(title_size * 0.10)
    ascent, descent = title_font.getmetrics()
    line_h = ascent + descent

    # Vertical layout: title block centered a touch above middle, subtitle near bottom.
    total_title_h = line_h * len(lines) + line_gap * (len(lines) - 1)
    title_top = int(CANVAS_H * 0.13)

    y = title_top
    for ln in lines:
        w = draw.textlength(ln, font=title_font)
        draw.text((panel_x0 + margin, y), ln, font=title_font, fill=style.text_color)
        y += line_h + line_gap

    # --- subtitle ---
    if style.subtitle.strip():
        sub_text = style.subtitle.upper() if style.uppercase else style.subtitle
        sub_size = max(18, int(title_size * 0.22))
        tracking_px = sub_size * style.subtitle_tracking
        # shrink subtitle until it fits with tracking
        while sub_size > 14:
            sub_font = _load_font(style.subtitle_weight, sub_size)
            tracking_px = sub_size * style.subtitle_tracking
            if _tracked_width(draw, sub_text, sub_font, tracking_px) <= text_max_w:
                break
            sub_size -= 2
        sub_font = _load_font(style.subtitle_weight, sub_size)
        tracking_px = sub_size * style.subtitle_tracking
        sub_y = int(CANVAS_H * 0.85)
        _draw_tracked(draw, (panel_x0 + margin, sub_y), sub_text, sub_font,
                      style.text_color, tracking_px)

    return canvas


def _cover_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """Scale + center-crop so the image exactly covers target_w x target_h."""
    if target_w <= 0 or target_h <= 0:
        return Image.new("RGB", (max(1, target_w), max(1, target_h)))
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = int(round(src_w * scale)), int(round(src_h * scale))
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


# ---------------------------------------------------------------------------
# Batch
# ---------------------------------------------------------------------------

def list_images(folder: str) -> list[str]:
    out = []
    for name in sorted(os.listdir(folder)):
        if os.path.splitext(name)[1].lower() in IMAGE_EXTS:
            out.append(os.path.join(folder, name))
    return out


def batch_render(input_folder: str, output_folder: str, style: Style,
                 titles: dict[str, str] | None = None, quality: int = 90,
                 progress=None) -> list[str]:
    """Render every image in input_folder to output_folder.

    titles: optional map of {filename: title} overriding the filename-derived title.
    progress: optional callback(done, total, current_name, error_or_none).
    Returns the list of written output paths.
    """
    os.makedirs(output_folder, exist_ok=True)
    images = list_images(input_folder)
    written = []
    total = len(images)
    titles = titles or {}
    for i, path in enumerate(images, 1):
        name = os.path.basename(path)
        err = None
        try:
            title = titles.get(name) or title_from_filename(path)
            img = render_thumbnail(path, title, style)
            stem = os.path.splitext(name)[0]
            out_path = os.path.join(output_folder, f"{stem}_thumb.jpg")
            img.save(out_path, "JPEG", quality=quality)
            written.append(out_path)
        except Exception as e:  # keep going on a bad file
            err = str(e)
        if progress:
            progress(i, total, name, err)
    return written
