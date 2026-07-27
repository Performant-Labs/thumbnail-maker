"""The UI-free config storage primitive: load/save round-trip and dir resolution."""

from __future__ import annotations

import json
import os

from core import config


def _redirect_config(monkeypatch, tmp_path):
    """Point config_dir() at a temp location on every platform."""
    monkeypatch.setenv("APPDATA", str(tmp_path))                 # win32
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))         # linux
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(tmp_path))  # macOS/home fallback


def test_config_dir_created(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    d = config.config_dir()
    assert os.path.isdir(d)
    assert d.endswith(config.APP_DIR_NAME)


def test_settings_path_under_config_dir(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    assert config.settings_path() == os.path.join(config.config_dir(), "settings.json")


def test_save_then_load_round_trip(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    data = {"single": {"title": "HELLO"}, "active_tab": 1, "custom_templates": ["/x/y.svg"]}
    config.save(data)
    assert json.load(open(config.settings_path(), encoding="utf-8")) == data
    assert config.load() == data


def test_load_missing_returns_empty_dict(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    assert config.load() == {}


def test_load_corrupt_returns_empty_dict(monkeypatch, tmp_path):
    _redirect_config(monkeypatch, tmp_path)
    with open(config.settings_path(), "w", encoding="utf-8") as f:
        f.write("{ not valid json")
    assert config.load() == {}
