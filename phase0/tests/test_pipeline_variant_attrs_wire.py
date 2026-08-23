"""Pipeline wiring: clean_variant_attributes drives row color/size/system."""
from adfeed.variant_attributes import clean_variant_attributes


def test_cleaner_output_maps_to_feed_row_keys():
    """Contract used by pipeline.generate_feed_for_store row builder."""
    cleaned = clean_variant_attributes(
        shopify_variant_id="41575567491130",
        color_raw="Blue",
        size_raw="L",
        title="Jeans",
        description="",
        gpc_path="Apparel > Jeans",
        sku="hex-sku",
    )
    row = {
        "颜色": cleaned.get("g_color") or "",
        "尺码": cleaned.get("g_size") or "",
        "size_system": cleaned.get("g_size_system") or "",
        "size_type": cleaned.get("g_size_type") or "",
    }
    assert row["颜色"] == "Blue"
    assert row["尺码"] == "L"
    assert row["size_system"] == "US"
    assert row["size_type"] == "Regular"
