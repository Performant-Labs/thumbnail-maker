"""Shared fixtures for the core test suite."""

from __future__ import annotations

import pytest
from PIL import Image


def _gradient(width: int = 1200, height: int = 1600) -> Image.Image:
    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        for x in range(width):
            px[x, y] = (x * 255 // width, y * 255 // height, 128)
    return img


@pytest.fixture
def sample_photo(tmp_path):
    """A generated JPEG photo (no sample committed to the repo)."""
    p = tmp_path / "feet-first.jpg"
    _gradient().save(p, "JPEG", quality=90)
    return str(p)


@pytest.fixture
def photo_folder(tmp_path):
    """A folder with three generated photos plus a non-image file to ignore."""
    folder = tmp_path / "photos"
    folder.mkdir()
    for name in ("alpha-one.jpg", "beta_two.png", "gamma three.jpg"):
        _gradient(600, 800).save(folder / name)
    (folder / "notes.txt").write_text("ignore me", encoding="utf-8")
    return str(folder)
