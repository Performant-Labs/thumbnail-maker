"""The CLI frontend is a pure core consumer: no tkinter, drives single + batch."""

from __future__ import annotations

import os
import subprocess
import sys

import cli


def test_importing_cli_does_not_import_tkinter():
    code = (
        "import sys, cli; "
        "assert 'tkinter' not in sys.modules and 'app' not in sys.modules, "
        "sorted(m for m in sys.modules if m in ('tkinter', 'app')); print('OK')"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert "OK" in proc.stdout


def test_cli_single_writes_thumbnail(sample_photo, tmp_path):
    rc = cli.main(["single", sample_photo, "--template", "editorial",
                   "--title", "FEET FIRST", "--out", str(tmp_path)])
    assert rc == 0
    assert os.path.isfile(tmp_path / "feet-first_thumb.jpg")


def test_cli_batch_writes_folder(photo_folder, tmp_path):
    out = tmp_path / "out"
    rc = cli.main(["batch", photo_folder, str(out), "--template", "right-panel"])
    assert rc == 0
    thumbs = sorted(p for p in os.listdir(out) if p.endswith("_thumb.jpg"))
    assert len(thumbs) == 3


def test_cli_batch_with_csv(photo_folder, tmp_path):
    csv_path = tmp_path / "t.csv"
    csv_path.write_text("filename,title\nalpha-one.jpg,Custom\n", encoding="utf-8")
    out = tmp_path / "out"
    rc = cli.main(["batch", photo_folder, str(out), "--csv", str(csv_path)])
    assert rc == 0
    assert len(os.listdir(out)) == 3


def test_cli_unknown_template_errors(sample_photo, tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        cli.main(["single", sample_photo, "--template", "nope", "--out", str(tmp_path)])


def test_cli_single_with_color_applies_panel_color(sample_photo, tmp_path):
    from PIL import Image

    rc = cli.main(["single", sample_photo, "--template", "editorial",
                   "--title", "FEET FIRST", "--color", "#112233", "--out", str(tmp_path)])
    assert rc == 0
    img = Image.open(tmp_path / "feet-first_thumb.jpg")
    pixel = img.getpixel((10, 10))
    # JPEG is lossy, so allow a little slack rather than requiring an exact match.
    assert all(abs(a - b) <= 8 for a, b in zip(pixel, (0x11, 0x22, 0x33)))


def test_cli_invalid_color_errors(sample_photo, tmp_path):
    import pytest

    with pytest.raises(SystemExit):
        cli.main(["single", sample_photo, "--color", "not-a-color", "--out", str(tmp_path)])
