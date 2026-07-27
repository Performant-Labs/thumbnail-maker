"""Boundary types passed across the front/back split.

These are plain data types with no UI knowledge, shared by core and every
frontend. Keeping them here (rather than in ``render``) makes the contract
explicit and import-cheap.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .resources import DEFAULT_SUBTITLE, DEFAULT_TEMPLATE, FONT_PATH

# Progress callback signature used by ``batch_render``:
#   progress(done, total, name, error) -> None
# ``error`` is None on success, else a message string.
ProgressCallback = Callable[[int, int, str, Optional[str]], None]


@dataclass
class Style:
    """Batch-wide render settings. The look itself comes from the template SVG."""

    template_path: str = DEFAULT_TEMPLATE
    subtitle: str = DEFAULT_SUBTITLE
    uppercase: bool = True
    font_files: list[str] = field(default_factory=lambda: [FONT_PATH])
