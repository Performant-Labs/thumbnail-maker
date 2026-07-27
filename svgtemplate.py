"""Editable SVG-template rendering engine.

A *template* is an ordinary SVG file you can design in any tool (Inkscape,
Illustrator, Figma, or by hand). The app fills it per photo and renders it to a
PNG/JPEG with resvg (a self-contained renderer — no system libraries needed).

Template contract
-----------------
1. Text tokens: put ``{{title}}`` and ``{{subtitle}}`` wherever you want them.
   Any other ``{{field}}`` is filled from an optional CSV (see render.py).
2. Photo region: give one element ``id="photo"`` (a ``<rect>`` placeholder is
   easiest). Each input photo is drawn into that element's box, cover-cropped
   (``preserveAspectRatio="xMidYMid slice"``), preserving any transform on it.
3. Auto-fit text (optional): on a ``<text>`` element add
   ``data-fit="true"`` with ``data-max-width`` (px), ``data-max-lines`` and
   optional ``data-line-height`` (default 1.05). The element's ``font-size`` is
   treated as the maximum; long titles shrink and wrap to fit.

Everything else in the SVG (colors, shapes, gradients, logos) renders as-is, so
the design is no longer hardcoded.
"""

from __future__ import annotations

import base64
import io
import os
import re
import xml.etree.ElementTree as ET

import resvg_py
from PIL import Image, ImageFont

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

_TOKEN_RE = re.compile(r"\{\{\s*([\w-]+)\s*\}\}")

_MIME = {
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
    ".webp": "image/webp", ".bmp": "image/bmp", ".gif": "image/gif",
    ".tif": "image/tiff", ".tiff": "image/tiff",
}


# ---------------------------------------------------------------------------
# Token substitution
# ---------------------------------------------------------------------------

def substitute_tokens(svg_text: str, fields: dict[str, str]) -> str:
    """Replace ``{{token}}`` occurrences with XML-escaped field values."""
    def repl(m):
        key = m.group(1)
        val = fields.get(key, "")
        return (val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    return _TOKEN_RE.sub(repl, svg_text)


# ---------------------------------------------------------------------------
# Photo injection
# ---------------------------------------------------------------------------

def _data_uri(photo_path: str) -> str:
    ext = os.path.splitext(photo_path)[1].lower()
    mime = _MIME.get(ext, "image/png")
    with open(photo_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _build_parent_map(root):
    return {child: parent for parent in root.iter() for child in parent}


def _inject_photo(root, photo_path: str):
    """Replace the element with id="photo" with an <image> of the photo."""
    target = None
    for el in root.iter():
        if el.get("id") == "photo":
            target = el
            break
    if target is None:
        return  # template has no photo slot; that's allowed

    x = target.get("x", "0")
    y = target.get("y", "0")
    w = target.get("width", "0")
    h = target.get("height", "0")
    transform = target.get("transform")

    img = ET.Element(f"{{{SVG_NS}}}image")
    img.set("x", x); img.set("y", y)
    img.set("width", w); img.set("height", h)
    img.set("preserveAspectRatio", "xMidYMid slice")
    img.set("href", _data_uri(photo_path))
    if transform:
        img.set("transform", transform)
    img.set("id", "photo")

    parents = _build_parent_map(root)
    parent = parents.get(target)
    if parent is None:
        return
    # replace in place to preserve stacking order
    idx = list(parent).index(target)
    parent.remove(target)
    parent.insert(idx, img)


# ---------------------------------------------------------------------------
# Auto-fit text
# ---------------------------------------------------------------------------

def _local(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


_WEIGHT_TO_VARIATION = {
    "300": "Regular", "400": "Regular", "normal": "Regular",
    "500": "Medium", "600": "SemiBold", "700": "Bold", "bold": "Bold",
    "800": "ExtraBold", "900": "Black",
}


def _fit_font(font_path: str, weight: str, size: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(font_path, size)
    try:
        font.set_variation_by_name(_WEIGHT_TO_VARIATION.get(str(weight), "Regular"))
    except Exception:
        pass
    return font


def _wrap(text: str, font: ImageFont.FreeTypeFont, max_w: float, max_lines: int):
    """Greedy word-wrap. Returns list of lines, or None if it can't fit."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for word in words[1:]:
        trial = f"{cur} {word}"
        if font.getlength(trial) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    lines.append(cur)
    if len(lines) > max_lines:
        return None
    if any(font.getlength(ln) > max_w for ln in lines):
        return None
    return lines


def _fit_text_elements(root, font_path: str, measure_weight_default: str = "400"):
    """Rewrite data-fit <text> elements with fitted size + wrapped tspans."""
    for el in root.iter():
        if _local(el.tag) != "text" or el.get("data-fit") not in ("true", "1", "yes"):
            continue
        text = "".join(el.itertext()).strip()
        max_w = float(el.get("data-max-width", "99999"))
        max_lines = int(el.get("data-max-lines", "2"))
        line_height = float(el.get("data-line-height", "1.05"))
        max_size = int(float(el.get("font-size", "100")))
        weight = el.get("font-weight", measure_weight_default)
        x = el.get("x", "0")

        size = max_size
        lines = None
        while size >= 12:
            font = _fit_font(font_path, weight, size)
            lines = _wrap(text, font, max_w, max_lines)
            if lines is not None:
                break
            size -= 2
        if lines is None:  # give up gracefully: single line at min size
            lines = [text]
            size = 12

        el.set("font-size", str(size))
        # rebuild children as tspans
        for child in list(el):
            el.remove(child)
        el.text = None
        line_dy = size * line_height
        for i, ln in enumerate(lines):
            tsp = ET.SubElement(el, f"{{{SVG_NS}}}tspan")
            tsp.set("x", x)
            tsp.set("dy", "0" if i == 0 else str(line_dy))
            tsp.text = ln


# ---------------------------------------------------------------------------
# Public render
# ---------------------------------------------------------------------------

def _canvas_size(root) -> tuple[int, int]:
    def num(v, default):
        if not v:
            return default
        m = re.match(r"([\d.]+)", v)
        return int(float(m.group(1))) if m else default
    w = num(root.get("width"), None)
    h = num(root.get("height"), None)
    if w and h:
        return w, h
    vb = root.get("viewBox")
    if vb:
        parts = vb.replace(",", " ").split()
        if len(parts) == 4:
            return int(float(parts[2])), int(float(parts[3]))
    return 1280, 720


def render_template(svg_text: str, photo_path: str, fields: dict[str, str],
                    font_files: list[str]) -> Image.Image:
    """Fill a template SVG with a photo + fields and render to a PIL Image."""
    filled = substitute_tokens(svg_text, fields)
    root = ET.fromstring(filled)

    _inject_photo(root, photo_path)
    font_for_measure = font_files[0] if font_files else None
    if font_for_measure:
        _fit_text_elements(root, font_for_measure)

    width, height = _canvas_size(root)
    out_svg = ET.tostring(root, encoding="unicode")

    png_bytes = resvg_py.svg_to_bytes(
        svg_string=out_svg,
        width=width,
        height=height,
        font_files=list(font_files),
        skip_system_fonts=True,
    )
    img = Image.open(io.BytesIO(bytes(png_bytes))).convert("RGBA")
    # flatten onto white so JPEG output has no black transparency
    bg = Image.new("RGB", img.size, "#FFFFFF")
    bg.paste(img, mask=img.split()[3])
    return bg
