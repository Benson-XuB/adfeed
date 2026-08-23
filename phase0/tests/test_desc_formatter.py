"""Description formatting for mashed attribute blobs."""
import re

from adfeed.desc_formatter import format_product_description, truncate_size_chart


def test_splits_glued_color_style():
    raw = "Color: BlueStyle: Private fashionFabric: CottonFit Type: Regular fit"
    out = format_product_description(raw)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    assert any(ln.startswith("Color:") and "Blue" in ln for ln in lines)
    assert any(ln.startswith("Style:") for ln in lines)
    assert any(ln.startswith("Fabric:") for ln in lines)
    assert "BlueStyle:" not in out
    assert len(lines) >= 3


def test_preserves_readable_multiline():
    raw = "Color: brown\nStyle: Streetwear\nFabric: PU"
    out = format_product_description(raw)
    assert "Color: brown" in out
    assert "Streetwear" in out


def test_fullwidth_punct_becomes_ascii():
    raw = "Color：Blue\nStyle：Streetwear，Fabric：Cotton"
    out = format_product_description(raw)
    assert "：" not in out
    assert "，" not in out
    assert "Color: Blue" in out
    assert "Streetwear, Fabric" in out or "Streetwear\n" in out


def test_truncates_size_measurement_table():
    raw = """Color: Blue
Style: Private fashion
Fabric: Cotton, Spandex
Fit Type: Regular fit
Gender: Unisex
Size: S, M, L, XL, XXL, XXXL
Size: unit: cm
Size
Waist/cm
Hip/cm
Length/cm
S
66
106
110
M
70
110
111"""
    out = format_product_description(raw)
    assert "Waist/cm" not in out
    assert "66" not in out
    assert "Size chart: see product page." in out
    assert "Color: Blue" in out
    assert "Fabric: Cotton" in out
    # all-size list above chart should be dropped
    assert not re.search(r"(?i)^Size:\s*S,\s*M", out, re.M)


def test_truncate_size_chart_standalone():
    raw = "Color: Red\nWaist/cm\n66\nHip/cm\n100"
    out = truncate_size_chart(raw)
    assert "Waist/cm" not in out
    assert "Size chart: see product page." in out
    assert "Color: Red" in out
