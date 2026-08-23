"""Variant attribute cleaner P0 — color/size/system/type for GMC feed rows."""
from adfeed.variant_attributes import clean_variant_attributes


def test_strips_noise_and_maps_color_size():
    out = clean_variant_attributes(
        shopify_variant_id="41575567491130",
        color_raw="黑色 现货",
        size_raw="升级款 M",
        title="Women Cotton Tee",
        description="",
        gpc_path="Apparel & Accessories > Clothing",
    )
    assert out["shopify_variant_id"] == "41575567491130"
    assert out["g_color"] == "Black"
    assert out["g_size"] == "M"
    assert out["g_size_system"] == "US"
    assert out["g_size_type"] == "Regular"


def test_empty_color_apparel_multicolor_not_default():
    out = clean_variant_attributes(
        shopify_variant_id="1",
        color_raw="",
        size_raw="",
        title="Boat Socks",
        description="no color words",
        gpc_path="Apparel > Socks",
        extract_color_fn=lambda t, d: "Multicolor",
    )
    assert out["g_color"] == "Multicolor"
    assert out["g_color"] != "Default"
    assert out["g_size"] == "One Size"
    assert out["g_size_system"] == "US"
    assert out["g_size_type"] == "Regular"


def test_non_apparel_skips_size_system():
    out = clean_variant_attributes(
        shopify_variant_id="2",
        color_raw="Black",
        size_raw="",
        title="USB Cable",
        description="",
        gpc_path="Electronics > Cables",
    )
    assert out["g_color"] == "Black"
    assert out.get("g_size_system") in ("", None)
    assert out.get("g_size_type") in ("", None)


def test_emits_va_events_for_fallbacks():
    out = clean_variant_attributes(
        shopify_variant_id="9",
        color_raw="",
        size_raw="",
        title="Dress",
        description="",
        gpc_path="Apparel > Dresses",
        extract_color_fn=lambda t, d: "Multicolor",
    )
    rules = {e.rule_id for e in out["events"]}
    assert "VA01" in rules  # color Multicolor
    assert "VA02" in rules  # One Size
    assert "VA03" in rules  # size_system/type


def test_opaque_style_axis_splits_key_not_pattern():
    """Style 1/2 are different garments — style_axis_key for item_group, not pattern/title."""
    from adfeed.attribute_normalizer import opaque_style_axis_key

    assert opaque_style_axis_key("Style 1") == "style-1"
    assert opaque_style_axis_key("Style 2") == "style-2"
    assert opaque_style_axis_key("Design A") == "design-a"
    assert opaque_style_axis_key("Black") == ""
    assert opaque_style_axis_key("Floral Print") == ""

    desc = "Color: brown\nStyle: Streetwear\nFabric: PU"
    a = clean_variant_attributes(
        shopify_variant_id="1",
        color_raw="Style 1",
        size_raw="L",
        title="Jacket",
        description=desc,
        gpc_path="Apparel & Accessories > Clothing > Outerwear",
    )
    b = clean_variant_attributes(
        shopify_variant_id="2",
        color_raw="Style 2",
        size_raw="L",
        title="Jacket",
        description=desc,
        gpc_path="Apparel & Accessories > Clothing > Outerwear",
    )
    assert a["g_color"] == "Brown" and b["g_color"] == "Brown"
    assert a["style_axis_key"] == "style-1"
    assert b["style_axis_key"] == "style-2"
    assert a["style_axis_key"] != b["style_axis_key"]
    assert "Style" not in (a.get("g_pattern") or "")
    assert "Style" not in (b.get("g_pattern") or "")


def test_real_color_option_has_no_style_axis():
    out = clean_variant_attributes(
        shopify_variant_id="3",
        color_raw="Navy Blue",
        size_raw="M",
        title="Dress",
        description="",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    assert out["g_color"] == "Navy Blue"
    assert out.get("style_axis_key") == ""
