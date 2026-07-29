"""Public rendering API: single render, layout preview, and batch (+progress +CSV)."""

from __future__ import annotations

import os

from PIL import Image

import core


def _style(**kw):
    return core.Style(template_path=core.DEFAULT_TEMPLATE, subtitle="20 MINUTE PRACTICE", **kw)


def test_render_thumbnail_returns_1280x720_rgb(sample_photo):
    img = core.render_thumbnail(sample_photo, "FEET FIRST", _style())
    assert isinstance(img, Image.Image)
    assert img.size == (1280, 720)
    assert img.mode == "RGB"


def test_render_thumbnail_accepts_field_dict(sample_photo):
    img = core.render_thumbnail(sample_photo, {"title": "HELLO", "subtitle": "SUB"}, _style())
    assert img.size == (1280, 720)


def test_render_layout_returns_image(sample_photo):
    img = core.render_layout(_style(), core.placeholder_fields("20 minute practice", True))
    assert isinstance(img, Image.Image)
    assert img.size == (1280, 720)


def test_render_thumbnail_applies_panel_color(sample_photo):
    # editorial.svg's id="panel" rect fills x=0..625, y=0..720.
    img = core.render_thumbnail(sample_photo, "FEET FIRST", _style(panel_color="#112233"))
    assert img.getpixel((10, 10)) == (0x11, 0x22, 0x33)


def test_render_thumbnail_invalid_panel_color_keeps_template_default(sample_photo):
    default_img = core.render_thumbnail(sample_photo, "FEET FIRST", _style())
    bad_img = core.render_thumbnail(sample_photo, "FEET FIRST", _style(panel_color="not-a-color"))
    assert bad_img.getpixel((10, 10)) == default_img.getpixel((10, 10))


def test_render_layout_defaults_fields():
    # fields=None path uses the style subtitle + a default title
    img = core.render_layout(_style())
    assert img.size == (1280, 720)


def test_batch_render_writes_thumbs_with_progress(photo_folder, tmp_path):
    out = tmp_path / "thumbnails"
    events = []

    def progress(done, total, name, err):
        events.append((done, total, name, err))

    written = core.batch_render(photo_folder, str(out), _style(), progress=progress)

    assert len(written) == 3
    for p in written:
        assert p.endswith("_thumb.jpg")
        assert os.path.isfile(p)
    # progress called once per image, with (done, total) counting up and no errors
    assert len(events) == 3
    assert [e[0] for e in events] == [1, 2, 3]
    assert all(e[1] == 3 for e in events)
    assert all(e[3] is None for e in events)


def test_batch_render_naming_matches_stem(photo_folder, tmp_path):
    out = tmp_path / "out"
    written = core.batch_render(photo_folder, str(out), _style())
    names = sorted(os.path.basename(p) for p in written)
    assert names == ["alpha-one_thumb.jpg", "beta_two_thumb.jpg", "gamma three_thumb.jpg"]


def test_batch_render_applies_csv_overrides(photo_folder, tmp_path):
    csv_path = tmp_path / "titles.csv"
    csv_path.write_text(
        "filename,title,subtitle\nalpha-one.jpg,Custom Title,Custom Sub\n",
        encoding="utf-8",
    )
    overrides = core.load_titles_csv(str(csv_path))
    assert "alpha-one.jpg" in overrides
    assert overrides["alpha-one.jpg"]["title"] == "Custom Title"

    out = tmp_path / "out"
    written = core.batch_render(photo_folder, str(out), _style(), csv_overrides=overrides)
    assert len(written) == 3  # override applied to one, others fall back to filename


def test_batch_render_skips_bad_file_and_reports(tmp_path):
    folder = tmp_path / "in"
    folder.mkdir()
    # A *directory* named like an image: it's listed by extension, but reading
    # its bytes raises -> render fails for that entry and the batch keeps going.
    (folder / "broken.jpg").mkdir()
    Image.new("RGB", (400, 400), "red").save(folder / "good.jpg")

    errors = []

    def progress(done, total, name, err):
        if err:
            errors.append((name, err))

    out = tmp_path / "out"
    written = core.batch_render(folder, str(out), _style(), progress=progress)
    assert len(written) == 1  # only the good one
    assert any(name == "broken.jpg" for name, _ in errors)
