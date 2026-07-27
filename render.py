"""Batch rendering: turn a folder of photos into thumbnails from an SVG template.

The visual design lives in an editable SVG template (see svgtemplate.py), not in
this code. This module handles file discovery, per-photo field values, and the
batch loop.
"""

from __future__ import annotations

import csv
import os
import sys
from dataclasses import dataclass, field

import svgtemplate

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

def _resource_dir() -> str:
    """Directory holding bundled data (fonts, templates).

    Under PyInstaller these are unpacked to sys._MEIPASS; otherwise it's the
    directory of this source file.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


FONT_PATH = os.path.join(_resource_dir(), "fonts", "PlayfairDisplay-VF.ttf")
TEMPLATES_DIR = os.path.join(_resource_dir(), "templates")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "editorial.svg")

DEFAULT_SUBTITLE = "20 MINUTE PRACTICE"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


@dataclass
class Style:
    """Batch-wide settings. The look itself comes from the template SVG."""

    template_path: str = DEFAULT_TEMPLATE
    subtitle: str = DEFAULT_SUBTITLE
    uppercase: bool = True
    font_files: list[str] = field(default_factory=lambda: [FONT_PATH])


# ---------------------------------------------------------------------------
# Titles / fields
# ---------------------------------------------------------------------------

def title_from_filename(path: str) -> str:
    """'feet-first.jpg' -> 'FEET FIRST' (case applied later)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for sep in ("_", "-", "."):
        stem = stem.replace(sep, " ")
    return " ".join(stem.split()).strip()


def load_titles_csv(csv_path: str) -> dict[str, dict[str, str]]:
    """Optional per-photo overrides.

    CSV with a 'filename' column plus any of 'title', 'subtitle', or custom
    fields. Returns {filename: {field: value}}.
    """
    out: dict[str, dict[str, str]] = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            name = (row.get("filename") or row.get("file") or "").strip()
            if name:
                out[name] = {k: (v or "") for k, v in row.items() if k}
    return out


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def list_images(folder: str) -> list[str]:
    return [
        os.path.join(folder, n)
        for n in sorted(os.listdir(folder))
        if os.path.splitext(n)[1].lower() in IMAGE_EXTS
    ]


def _fields_for(path: str, style: Style, overrides: dict[str, str] | None) -> dict[str, str]:
    overrides = overrides or {}
    title = overrides.get("title") or title_from_filename(path)
    subtitle = overrides.get("subtitle") or style.subtitle
    if style.uppercase:
        title = title.upper()
        subtitle = subtitle.upper()
    fields = {k: v for k, v in overrides.items() if k not in ("filename", "file")}
    fields["title"] = title
    fields["subtitle"] = subtitle
    return fields


def render_thumbnail(photo_path: str, title_or_fields, style: Style):
    """Render one thumbnail to a PIL Image.

    title_or_fields may be a plain title string or a dict of field overrides.
    """
    overrides = title_or_fields if isinstance(title_or_fields, dict) else {"title": title_or_fields}
    with open(style.template_path, encoding="utf-8") as f:
        svg = f.read()
    fields = _fields_for(photo_path, style, overrides)
    return svgtemplate.render_template(svg, photo_path, fields, style.font_files)


def batch_render(input_folder: str, output_folder: str, style: Style,
                 csv_overrides: dict[str, dict[str, str]] | None = None,
                 quality: int = 90, progress=None) -> list[str]:
    """Render every image in input_folder to output_folder.

    progress: optional callback(done, total, current_name, error_or_none).
    Returns the list of written output paths.
    """
    os.makedirs(output_folder, exist_ok=True)
    with open(style.template_path, encoding="utf-8") as f:
        svg = f.read()
    csv_overrides = csv_overrides or {}
    images = list_images(input_folder)
    written, total = [], len(images)
    for i, path in enumerate(images, 1):
        name = os.path.basename(path)
        err = None
        try:
            fields = _fields_for(path, style, csv_overrides.get(name))
            img = svgtemplate.render_template(svg, path, fields, style.font_files)
            out_path = os.path.join(output_folder, f"{os.path.splitext(name)[0]}_thumb.jpg")
            img.save(out_path, "JPEG", quality=quality)
            written.append(out_path)
        except Exception as e:  # keep going on a bad file
            err = str(e)
        if progress:
            progress(i, total, name, err)
    return written
