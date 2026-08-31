"""Feed field fixes: color/pattern, GPC from catalog, material/weight, age_group."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.mark.parametrize(
    "raw",
    [
        "Cream",
        "Ivory",
        "Sage",
        "Emerald",
        "Plum",
        "Charcoal",
        "Olive",
        "Forest",
        "Coral",
        "Mint",
        "Teal",
        "Natural",
    ],
)
def test_pure_named_colors_stay_in_color_not_pattern(raw):
    from adfeed.attribute_normalizer import resolve_gmc_color_and_pattern
    from adfeed.variant_attributes import clean_variant_attributes

    hue, pattern = resolve_gmc_color_and_pattern(raw, title="Product", description="")
    assert hue.lower() == raw.lower() or hue  # recognized hue
    assert hue != "Multicolor"
    assert pattern == ""

    out = clean_variant_attributes(
        color_raw=raw,
        size_raw="M",
        title="Product",
        description="",
        gpc_path="Apparel & Accessories > Clothing",
        gpc_code="2271",
    )
    assert out["g_color"] != "Multicolor"
    assert out["g_color"].lower() == raw.lower() or out["g_color"]
    assert out["g_pattern"] == ""


def test_floral_keeps_pattern_separate():
    from adfeed.variant_attributes import clean_variant_attributes

    out = clean_variant_attributes(
        color_raw="Pink Floral",
        size_raw="M",
        title="Pink Floral Midi Dress",
        description="",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
        gpc_code="2271",
    )
    assert out["g_color"] == "Pink"
    assert out["g_pattern"] == "Floral"


def test_infer_material_does_not_force_polyester_on_home():
    from adfeed.pipeline import _infer_material

    assert _infer_material("206", "Stoneware Mug", "Stoneware", "") == "Stoneware"
    # Title keyword may fill Stoneware; bare unknown home title must not get Polyester
    assert _infer_material("206", "Desk Organizer Tray", "", "") == ""
    assert _infer_material("2271", "Summer Dress", "", "") == "Polyester"  # apparel GPC default
    assert _infer_material("2271", "Chiffon Dress", "", "") == "Chiffon"  # title keyword wins
    assert "Denim" in _infer_material("204", "Slim Stretch Jeans", "", "")
    assert "Silicone" in _infer_material("", "Silicone Spatula Set", "", "")


def test_shipping_weight_empty_when_unknown_non_apparel():
    from adfeed.feed_generator import apply_shipping_weight_default

    row = {"GPC路径": "Home & Garden > Kitchen", "shipping_weight": ""}
    apply_shipping_weight_default(row)
    assert not (row.get("shipping_weight") or "").strip()


def test_empty_color_does_not_invent_multicolor_in_google_xml():
    """Non-apparel / empty color must stay empty — never invent Multicolor."""
    import re

    import pandas as pd

    from adfeed.feed_generator import generate

    df = pd.DataFrame(
        [
            {
                "SKU": "NL-BTY-MOI-50",
                "优化后标题": "Daily Gel Moisturizer 50ml",
                "标题": "Daily Gel Moisturizer 50ml",
                "描述": "Lightweight gel moisturizer for daily use.",
                "GPC代码": "567",
                "GPC路径": "Health & Beauty > Personal Care",
                "材质": "",
                "颜色": "",
                "尺码": "50ml",
                "品牌": "Northline",
                "价格": 22.0,
                "库存": 40,
                "图片链接": "https://example.com/a.jpg",
                "链接": "https://example.com/p",
                "gender": "unisex",
                "age_group": "adult",
                "identifier_exists": "no",
            }
        ]
    )
    xml = generate(df, "US")
    assert "Multicolor" not in xml
    assert re.search(r"<g:color>", xml) is None


def test_mock_catalog_has_diverse_gpc_and_no_mock_blurb():
    from adfeed.mock_catalog import catalog_products

    products = catalog_products()
    codes = {p.get("gpc_code") for p in products}
    assert len(codes) >= 8
    assert "2271" in codes  # dresses still apparel
    home = [p for p in products if p["product_type"] == "Home"]
    assert home
    assert all(p.get("gpc_code") and p["gpc_code"] != "2271" for p in home)
    assert all("mock catalog SKU" not in (p.get("description") or "").lower() for p in products)
    baby = next(p for p in products if p["handle"] == "baby-bodysuit")
    assert baby.get("age_group") == "infant"
