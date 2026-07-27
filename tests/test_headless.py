"""The core backend must be fully UI-free and importable with no display.

These tests assert that importing ``core`` pulls in no GUI toolkit (no
``tkinter``, no ``PIL.ImageTk``), so the backend runs unchanged in a headless
CI environment.
"""

from __future__ import annotations

import subprocess
import sys


def test_import_core_pulls_in_no_tkinter():
    """After `import core`, tkinter/ImageTk must not be in sys.modules.

    Run in a fresh interpreter so a GUI import elsewhere in the test session
    can't mask a real dependency in core's import graph.
    """
    code = (
        "import sys; import core; "
        "bad = [m for m in sys.modules "
        "if m == 'tkinter' or m.startswith('tkinter.') or m == 'PIL.ImageTk']; "
        "assert not bad, bad; print('OK')"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, (
        f"import core pulled in GUI modules or failed:\n"
        f"STDOUT: {proc.stdout}\nSTDERR: {proc.stderr}"
    )
    assert "OK" in proc.stdout


def test_core_source_files_do_not_reference_tkinter():
    """No module in the core package should import tkinter or ImageTk."""
    import pathlib
    import re

    import core

    # Match real import statements, not prose in docstrings/comments.
    gui_import = re.compile(
        r"^\s*(?:import\s+tkinter|from\s+tkinter\b|from\s+PIL\s+import\s+.*\bImageTk\b|import\s+PIL\.ImageTk)",
        re.MULTILINE,
    )
    pkg_dir = pathlib.Path(core.__file__).parent
    offenders = []
    for py in pkg_dir.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if gui_import.search(text):
            offenders.append(py.name)
    assert not offenders, f"core modules import a GUI toolkit: {offenders}"


def test_import_core_succeeds_headlessly():
    """`import core` and access to the public API works in-process."""
    import core

    assert hasattr(core, "render_thumbnail")
    assert hasattr(core, "batch_render")
    assert hasattr(core, "render_layout")
    assert "Style" in core.__all__
