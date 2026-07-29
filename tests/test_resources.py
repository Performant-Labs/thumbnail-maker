"""Bundled resource resolution: the panel-color list from templates/colors.json."""

from __future__ import annotations

import json

import core
from core.resources import load_panel_colors


def test_load_panel_colors_reads_bundled_file():
    colors = core.load_panel_colors()
    assert len(colors) >= 1
    assert all(set(c) == {"name", "hex"} for c in colors)
    assert all(core.is_valid_hex_color(c["hex"]) for c in colors)


def test_load_panel_colors_missing_file_returns_empty(tmp_path):
    assert load_panel_colors(str(tmp_path / "nope.json")) == []


def test_load_panel_colors_malformed_json_returns_empty(tmp_path):
    p = tmp_path / "colors.json"
    p.write_text("{ not valid json", encoding="utf-8")
    assert load_panel_colors(str(p)) == []


def test_load_panel_colors_ignores_malformed_entries(tmp_path):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps([
        {"name": "Good", "hex": "#123456"},
        {"name": "Missing hex"},
        "not-a-dict",
    ]), encoding="utf-8")
    assert load_panel_colors(str(p)) == [{"name": "Good", "hex": "#123456"}]


def test_load_panel_colors_non_list_returns_empty(tmp_path):
    p = tmp_path / "colors.json"
    p.write_text(json.dumps({"name": "Good", "hex": "#123456"}), encoding="utf-8")
    assert load_panel_colors(str(p)) == []
