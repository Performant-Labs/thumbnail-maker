"""Bundled-resource resolution for the core library.

`templates/` and `fonts/` live at the repository root, next to the `core/`
package. This module resolves them in both a source checkout and a PyInstaller
frozen build, and exposes the resource-path constants the rest of core uses.
"""

from __future__ import annotations

import json
import os
import sys

# ---------------------------------------------------------------------------
# Resource directory
# ---------------------------------------------------------------------------

def _resource_dir() -> str:
    """Directory holding bundled data (fonts, templates).

    Under PyInstaller these are unpacked to ``sys._MEIPASS``; otherwise it's the
    repository root, i.e. the parent of this ``core/`` package (fonts/ and
    templates/ sit next to core/, not inside it).
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    # core/resources.py -> core/ -> repo root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


FONT_PATH = os.path.join(_resource_dir(), "fonts", "PlayfairDisplay-VF.ttf")
TEMPLATES_DIR = os.path.join(_resource_dir(), "templates")
DEFAULT_TEMPLATE = os.path.join(TEMPLATES_DIR, "editorial.svg")
PANEL_COLORS_PATH = os.path.join(TEMPLATES_DIR, "colors.json")

DEFAULT_SUBTITLE = "20 MINUTE PRACTICE"
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def load_panel_colors(path: str = PANEL_COLORS_PATH) -> list[dict[str, str]]:
    """Named panel-color choices: ``[{"name": ..., "hex": ...}, ...]``.

    Missing/unreadable/malformed file -> empty list, so a broken or absent
    colors.json degrades to "no dropdown entries" rather than a crash.
    """
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [
        {"name": str(e["name"]), "hex": str(e["hex"])}
        for e in data
        if isinstance(e, dict) and "name" in e and "hex" in e
    ]
