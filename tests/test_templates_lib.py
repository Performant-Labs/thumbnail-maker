"""Template library: built-in vs custom classification and label/path resolution."""

from __future__ import annotations

import shutil

import core
from core.templates_lib import TemplateLibrary, builtin_template_paths


def test_builtins_load_and_classify():
    lib = TemplateLibrary()
    lib.load_builtins()
    labels = lib.labels()
    assert "editorial" in labels
    # All five shipped templates are present and classified built-in.
    for name in ("editorial", "right-panel", "bottom-bar", "lower-third", "top-banner"):
        assert name in labels, name
        assert lib.is_builtin(lib.path_for_label(name)), name
    assert set(lib.builtin_labels()) == set(labels)
    assert lib.custom_labels() == []


def test_builtin_template_paths_lists_five():
    paths = builtin_template_paths()
    assert len(paths) == 5
    assert all(p.endswith(".svg") for p in paths)


def test_custom_registration_and_classification(tmp_path):
    lib = TemplateLibrary()
    lib.load_builtins()
    custom = tmp_path / "my-look.svg"
    shutil.copyfile(lib.path_for_label("editorial"), custom)

    label = lib.add(str(custom))
    assert label == "my-look"
    assert label in lib.custom_labels()
    assert label not in lib.builtin_labels()
    assert not lib.is_builtin(str(custom))
    assert str(custom) in (str(p) for p in lib.custom_paths())


def test_registration_is_idempotent_by_path(tmp_path):
    lib = TemplateLibrary()
    custom = tmp_path / "dup.svg"
    custom.write_text("<svg/>", encoding="utf-8")
    a = lib.register(str(custom))
    b = lib.register(str(custom))
    assert a == b
    assert lib.labels().count(a) == 1


def test_label_collision_gets_suffix(tmp_path):
    lib = TemplateLibrary()
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    (d1 / "same.svg").write_text("<svg/>", encoding="utf-8")
    (d2 / "same.svg").write_text("<svg/>", encoding="utf-8")
    l1 = lib.register(str(d1 / "same.svg"))
    l2 = lib.register(str(d2 / "same.svg"))
    assert l1 == "same"
    assert l2 == "same (2)"


def test_path_for_unknown_label_falls_back_to_default():
    lib = TemplateLibrary()
    lib.load_builtins()
    assert lib.path_for_label("does-not-exist") == core.DEFAULT_TEMPLATE


def test_label_for_path_defaults_to_editorial():
    lib = TemplateLibrary()
    lib.load_builtins()
    assert lib.label_for_path(None) == "editorial"
    assert lib.label_for_path(core.DEFAULT_TEMPLATE) == "editorial"
