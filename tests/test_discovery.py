"""Image discovery, title derivation, and placeholder-field generation."""

from __future__ import annotations

import os

import core


def test_title_from_filename_separators():
    assert core.title_from_filename("/a/feet-first.jpg") == "feet first"
    assert core.title_from_filename("rebuild_your_foundation.png") == "rebuild your foundation"
    assert core.title_from_filename("hip.openers.jpg") == "hip openers"
    assert core.title_from_filename("/x/already spaced.jpg") == "already spaced"


def test_list_images_sorted_and_filtered(photo_folder):
    images = core.list_images(photo_folder)
    assert len(images) == 3  # notes.txt ignored
    names = [os.path.basename(p) for p in images]
    assert names == sorted(names)
    assert all(os.path.splitext(p)[1].lower() in core.IMAGE_EXTS for p in images)
    assert "notes.txt" not in names


def test_list_images_empty_folder(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    assert core.list_images(str(d)) == []


def test_placeholder_fields_uppercase():
    f = core.placeholder_fields("20 minute practice", uppercase=True)
    assert f == {"title": "YOUR TITLE HERE", "subtitle": "20 MINUTE PRACTICE"}


def test_placeholder_fields_mixed_case_and_empty_subtitle():
    f = core.placeholder_fields("", uppercase=False)
    assert f == {"title": "Your Title Here", "subtitle": "Subtitle"}
