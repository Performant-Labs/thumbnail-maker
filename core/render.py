"""Batch rendering: turn a folder of photos into thumbnails from an SVG template.

The visual design lives in an editable SVG template (see svgtemplate.py), not in
this code. This module handles file discovery, per-photo field values, and the
batch loop.
"""

from __future__ import annotations

import csv
import os

from . import svgtemplate
from .resources import (
    DEFAULT_SUBTITLE,
    DEFAULT_TEMPLATE,
    FONT_PATH,
    IMAGE_EXTS,
    TEMPLATES_DIR,
)
from .types import Style

__all__ = [
    "Style",
    "DEFAULT_TEMPLATE",
    "TEMPLATES_DIR",
    "FONT_PATH",
    "DEFAULT_SUBTITLE",
    "IMAGE_EXTS",
    "title_from_filename",
    "load_titles_csv",
    "list_images",
    "placeholder_fields",
    "render_thumbnail",
    "render_layout",
    "batch_render",
]


# ---------------------------------------------------------------------------
# Titles / fields
# ---------------------------------------------------------------------------

def title_from_filename(path: str) -> str:
    """'feet-first.jpg' -> 'FEET FIRST' (case applied later)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    for sep in ("_", "-", "."):
        stem = stem.replace(sep, " ")
    return " ".join(stem.split()).strip()


def placeholder_fields(subtitle: str, uppercase: bool) -> dict[str, str]:
    """Field dict for a layout preview before a real title exists.

    Produces the placeholder title ("Your Title Here") plus the given subtitle,
    applying the same uppercase rule as a real render. This is domain logic, not
    presentation, so it lives in core and is shared by every frontend.
    """
    title = "Your Title Here"
    subtitle = subtitle or "Subtitle"
    if uppercase:
        title, subtitle = title.upper(), subtitle.upper()
    return {"title": title, "subtitle": subtitle}


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
    return svgtemplate.render_template(svg, photo_path, fields, style.font_files,
                                       panel_color=style.panel_color)


def render_layout(style: Style, fields: dict[str, str] | None = None):
    """Render the template's layout (placeholder words + a 'PHOTO' box)."""
    fields = fields or {"title": "Your Title Here", "subtitle": style.subtitle}
    with open(style.template_path, encoding="utf-8") as f:
        svg = f.read()
    return svgtemplate.render_layout(svg, fields, style.font_files, panel_color=style.panel_color)


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
            img = svgtemplate.render_template(svg, path, fields, style.font_files,
                                              panel_color=style.panel_color)
            out_path = os.path.join(output_folder, f"{os.path.splitext(name)[0]}_thumb.jpg")
            img.save(out_path, "JPEG", quality=quality)
            written.append(out_path)
        except Exception as e:  # keep going on a bad file
            err = str(e)
        if progress:
            progress(i, total, name, err)
    return written
