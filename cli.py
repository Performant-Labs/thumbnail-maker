"""Thumbnail Maker — command-line frontend.

A second consumer of the exact same backend as the GUI, to prove the front/back
split: it imports **only** ``core`` (plus stdlib) and never touches ``app`` or
tkinter.

Usage:
    python cli.py single <image> [--template NAME] [--title "..."]
                                 [--subtitle "..."] [--no-uppercase]
                                 [--color "#RRGGBB"] [--out DIR] [--quality N]
    python cli.py batch <input_dir> <output_dir> [--template NAME]
                                 [--subtitle "..."] [--no-uppercase]
                                 [--color "#RRGGBB"] [--csv FILE] [--quality N]
    python cli.py templates          # list available built-in template names

``--template`` takes a built-in template *name* (e.g. ``editorial``,
``right-panel``) or a path to any ``.svg`` file.
"""

from __future__ import annotations

import argparse
import os
import sys

import core


def _resolve_template(name: str | None) -> str:
    """Map a --template value (built-in name or path) to a template path."""
    if not name:
        return core.DEFAULT_TEMPLATE
    if os.path.isfile(name):
        return os.path.abspath(name)
    lib = core.TemplateLibrary()
    lib.load_builtins()
    for label in lib.labels():
        if label == name:
            return lib.path_for_label(label)
    available = ", ".join(lib.labels())
    raise SystemExit(f"Unknown template {name!r}. Available: {available} (or pass an .svg path).")


def _panel_color(value: str | None) -> str | None:
    if value is None:
        return None
    if not core.is_valid_hex_color(value):
        raise SystemExit(f"Invalid --color {value!r}: expected #RGB or #RRGGBB.")
    return value


def _style(args) -> core.Style:
    return core.Style(
        template_path=_resolve_template(args.template),
        subtitle=args.subtitle,
        uppercase=not args.no_uppercase,
        panel_color=_panel_color(args.color),
    )


def cmd_single(args) -> int:
    image = args.image
    if not os.path.isfile(image):
        raise SystemExit(f"No such image: {image}")
    out_dir = args.out or os.path.dirname(os.path.abspath(image))
    os.makedirs(out_dir, exist_ok=True)

    title = args.title or core.title_from_filename(image)
    img = core.render_thumbnail(image, title, _style(args))
    stem = os.path.splitext(os.path.basename(image))[0]
    out_path = os.path.join(out_dir, f"{stem}_thumb.jpg")
    img.save(out_path, "JPEG", quality=args.quality)
    print(f"Wrote {out_path}")
    return 0


def cmd_batch(args) -> int:
    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"No such input folder: {args.input_dir}")
    overrides = core.load_titles_csv(args.csv) if args.csv else None

    def progress(done, total, name, err):
        status = "ERROR: " + err if err else "ok"
        print(f"[{done}/{total}] {name} — {status}")

    written = core.batch_render(
        args.input_dir, args.output_dir, _style(args),
        csv_overrides=overrides, quality=args.quality, progress=progress,
    )
    print(f"Done. Wrote {len(written)} thumbnail(s) to {args.output_dir}.")
    return 0


def cmd_templates(_args) -> int:
    lib = core.TemplateLibrary()
    lib.load_builtins()
    print("Built-in templates:")
    for label in lib.builtin_labels():
        print(f"  {label}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="cli.py", description="Thumbnail Maker CLI (uses core, no GUI).")
    sub = p.add_subparsers(dest="command", required=True)

    def add_style_opts(sp):
        sp.add_argument("--template", help="Built-in template name or path to an .svg")
        sp.add_argument("--subtitle", default=core.DEFAULT_SUBTITLE, help="Subtitle text")
        sp.add_argument("--no-uppercase", action="store_true", help="Do not uppercase title/subtitle")
        sp.add_argument("--quality", type=int, default=90, help="JPEG quality (default 90)")
        sp.add_argument("--color", help="Panel background color as #RGB or #RRGGBB "
                                        "(overrides the template's default fill)")

    sp_single = sub.add_parser("single", help="Render one thumbnail from one image")
    sp_single.add_argument("image", help="Path to the source photo")
    sp_single.add_argument("--title", help="Title text (default: derived from filename)")
    sp_single.add_argument("--out", help="Output folder (default: alongside the image)")
    add_style_opts(sp_single)
    sp_single.set_defaults(func=cmd_single)

    sp_batch = sub.add_parser("batch", help="Render a whole folder of images")
    sp_batch.add_argument("input_dir", help="Folder of source photos")
    sp_batch.add_argument("output_dir", help="Folder to write thumbnails into")
    sp_batch.add_argument("--csv", help="Optional per-photo titles CSV")
    add_style_opts(sp_batch)
    sp_batch.set_defaults(func=cmd_batch)

    sp_templates = sub.add_parser("templates", help="List built-in template names")
    sp_templates.set_defaults(func=cmd_templates)

    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
