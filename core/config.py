"""UI-free settings persistence — a core storage primitive.

This is the storage *primitive* only: load/save an untyped dict plus config-dir
resolution. The *schema* of that dict (per-tab blocks, custom-template list,
etc.) is owned by the frontend. No UI toolkit is imported here.

Stored as JSON in the per-user config directory:
  Windows: %APPDATA%\ThumbnailMaker\settings.json
  macOS:   ~/Library/Application Support/ThumbnailMaker/settings.json
  Linux:   ~/.config/ThumbnailMaker/settings.json
"""

from __future__ import annotations

import json
import os
import sys

__all__ = ["APP_DIR_NAME", "config_dir", "settings_path", "load", "save"]

APP_DIR_NAME = "ThumbnailMaker"


def config_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    d = os.path.join(base, APP_DIR_NAME)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def settings_path() -> str:
    return os.path.join(config_dir(), "settings.json")


def load() -> dict:
    try:
        with open(settings_path(), encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save(data: dict) -> None:
    try:
        with open(settings_path(), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError:
        pass  # never let a settings write crash the app
