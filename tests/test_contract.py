"""The template/render contract: tokens, id="photo" slice, data-fit shrink+wrap."""

from __future__ import annotations

import xml.etree.ElementTree as ET

import core
from core import svgtemplate

SVG_NS = "http://www.w3.org/2000/svg"


def test_token_substitution_and_xml_escaping():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>{{title}}</text></svg>'
    out = svgtemplate.substitute_tokens(svg, {"title": "A & B < C"})
    assert "A &amp; B &lt; C" in out
    assert "{{title}}" not in out


def test_missing_token_becomes_empty():
    svg = "{{title}}-{{missing}}"
    out = svgtemplate.substitute_tokens(svg, {"title": "X"})
    assert out == "X-"


def test_photo_slot_replaced_with_cover_cropped_image(sample_photo):
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
        '<rect id="photo" x="100" y="0" width="655" height="720"/></svg>'
    )
    root = ET.fromstring(svg)
    svgtemplate._inject_photo(root, sample_photo)
    imgs = [el for el in root.iter() if el.tag == f"{{{SVG_NS}}}image"]
    assert len(imgs) == 1
    img = imgs[0]
    # cover-crop slice + geometry preserved from the placeholder
    assert img.get("preserveAspectRatio") == "xMidYMid slice"
    assert img.get("x") == "100" and img.get("width") == "655"
    assert img.get("href", "").startswith("data:image/")
    # the original rect placeholder is gone
    assert not [el for el in root.iter() if el.tag == f"{{{SVG_NS}}}rect" and el.get("id") == "photo"]


def test_layout_placeholder_draws_photo_box():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
        '<rect id="photo" x="0" y="0" width="640" height="720"/></svg>'
    )
    root = ET.fromstring(svg)
    svgtemplate._inject_photo_placeholder(root)
    texts = [el for el in root.iter() if el.tag == f"{{{SVG_NS}}}text"]
    assert any((t.text or "") == "PHOTO" for t in texts)


def test_data_fit_shrinks_and_wraps_long_title():
    # Narrow max-width forces a long title to shrink below the max font-size
    # and wrap into <= max-lines tspans.
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
        '<text x="50" y="200" font-family="Playfair Display" font-size="170"'
        ' data-fit="true" data-max-width="500" data-max-lines="2">'
        'A VERY LONG TITLE THAT CANNOT POSSIBLY FIT ON ONE LINE</text></svg>'
    )
    root = ET.fromstring(svg)
    svgtemplate._fit_text_elements(root, core.FONT_PATH)
    text_el = [el for el in root.iter() if el.tag == f"{{{SVG_NS}}}text"][0]
    final_size = int(float(text_el.get("font-size")))
    assert final_size < 170, "font-size should shrink below the max"
    tspans = [el for el in text_el.iter() if el.tag == f"{{{SVG_NS}}}tspan"]
    assert 1 <= len(tspans) <= 2, "should wrap within max-lines"


def test_data_fit_short_title_keeps_max_size():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="720">'
        '<text x="50" y="200" font-family="Playfair Display" font-size="120"'
        ' data-fit="true" data-max-width="1000" data-max-lines="2">HI</text></svg>'
    )
    root = ET.fromstring(svg)
    svgtemplate._fit_text_elements(root, core.FONT_PATH)
    text_el = [el for el in root.iter() if el.tag == f"{{{SVG_NS}}}text"][0]
    assert int(float(text_el.get("font-size"))) == 120


def test_is_valid_hex_color():
    assert svgtemplate.is_valid_hex_color("#72204E")
    assert svgtemplate.is_valid_hex_color("#abc")
    assert not svgtemplate.is_valid_hex_color("72204E")   # missing '#'
    assert not svgtemplate.is_valid_hex_color("#72204")   # wrong length
    assert not svgtemplate.is_valid_hex_color("#zzzzzz")  # not hex digits
    assert not svgtemplate.is_valid_hex_color("")
    assert not svgtemplate.is_valid_hex_color(None)


def test_inject_panel_color_overrides_fill():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect id="panel" x="0" y="0" width="625" height="720" fill="#72204E"/></svg>'
    )
    root = ET.fromstring(svg)
    svgtemplate._inject_panel_color(root, "#123456")
    panel = [el for el in root.iter() if el.get("id") == "panel"][0]
    assert panel.get("fill") == "#123456"


def test_inject_panel_color_noop_without_panel_element():
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><rect x="0" y="0" width="10" height="10"/></svg>'
    root = ET.fromstring(svg)
    svgtemplate._inject_panel_color(root, "#123456")  # must not raise
    assert "#123456" not in ET.tostring(root, encoding="unicode")


def test_inject_panel_color_noop_on_invalid_or_missing_color():
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg">'
        '<rect id="panel" fill="#72204E"/></svg>'
    )
    for bad in (None, "", "not-a-color"):
        root = ET.fromstring(svg)
        svgtemplate._inject_panel_color(root, bad)
        panel = [el for el in root.iter() if el.get("id") == "panel"][0]
        assert panel.get("fill") == "#72204E"


def test_all_five_builtin_templates_render(sample_photo):
    """Every shipped template renders both a short and a long title to 1280x720."""
    for path in core.builtin_template_paths():
        style = core.Style(template_path=path, subtitle="20 MINUTE PRACTICE")
        for title in ("HI", "A VERY LONG EDITORIAL TITLE THAT MUST SHRINK AND WRAP"):
            img = core.render_thumbnail(sample_photo, title, style)
            assert img.size == (1280, 720), path
