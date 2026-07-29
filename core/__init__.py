"""Thumbnail Maker core — the UI-free backend.

This package renders thumbnails from editable SVG templates, discovers images,
derives titles, classifies the template library, and persists raw settings. It
imports no GUI toolkit (no ``tkinter``, no ``PIL.ImageTk``) and returns PIL
``Image`` objects or writes files — never Tk objects.

Frontends (the tkinter GUI in ``app.py``, ``cli.py``) depend only on the names
re-exported here (see ``__all__``) plus ``core.config``. See
``docs/architecture.md`` for the full boundary description.
"""

from __future__ import annotations

from . import config
from .resources import (
    DEFAULT_SUBTITLE,
    DEFAULT_TEMPLATE,
    FONT_PATH,
    IMAGE_EXTS,
    PANEL_COLORS_PATH,
    TEMPLATES_DIR,
    load_panel_colors,
)
from .render import (
    batch_render,
    list_images,
    load_titles_csv,
    placeholder_fields,
    render_layout,
    render_thumbnail,
    title_from_filename,
)
from .svgtemplate import is_valid_hex_color
from .templates_lib import TemplateLibrary, builtin_template_paths
from .types import ProgressCallback, Style

__all__ = [
    # types
    "Style",
    "ProgressCallback",
    # resource constants
    "DEFAULT_TEMPLATE",
    "TEMPLATES_DIR",
    "FONT_PATH",
    "DEFAULT_SUBTITLE",
    "IMAGE_EXTS",
    "PANEL_COLORS_PATH",
    # rendering
    "render_thumbnail",
    "render_layout",
    "batch_render",
    # discovery / titles / fields
    "title_from_filename",
    "list_images",
    "load_titles_csv",
    "placeholder_fields",
    # panel color
    "load_panel_colors",
    "is_valid_hex_color",
    # template library / classification
    "TemplateLibrary",
    "builtin_template_paths",
    # config persistence (also available as core.config)
    "config",
]
