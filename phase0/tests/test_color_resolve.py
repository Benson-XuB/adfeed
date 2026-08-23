"""Color stays a GMC hue; print/Style go to pattern (field contract)."""
from adfeed.attribute_normalizer import (
    extract_pattern_from_color_raw,
    parse_listed_colors,
    resolve_gmc_color,
    resolve_gmc_color_and_pattern,
)


def test_strip_marketing_suffix_from_color():
    assert resolve_gmc_color("Black [10a antibacterial]") == "Black"
    assert resolve_gmc_color("Dark gray [10a antibacterial]") == "Dark Gray"
    assert resolve_gmc_color("White (anti-odor* breathable)") == "White"


def test_style_maps_from_description_color_list():
    desc = "Color: Black, Khaki\nStyle: Streetwear\nFabric: PU"
    assert resolve_gmc_color("Style 1", description=desc) == "Black"
    assert resolve_gmc_color("Style 2", description=desc) == "Khaki"


def test_style_same_desc_color_splits_pattern():
    """Style N is not a searchable pattern — never invent Style into pattern/title."""
    desc = "Color: brown\nStyle: Streetwear"
    c1, p1 = resolve_gmc_color_and_pattern("Style 1", description=desc)
    c2, p2 = resolve_gmc_color_and_pattern("Style 2", description=desc)
    assert c1 == "Brown" and c2 == "Brown"
    assert p1 == "" and p2 == ""


def test_parse_listed_colors():
    assert parse_listed_colors("Color: Black, White") == ["Black", "White"]
    assert parse_listed_colors("Color: brown") == ["Brown"]


def test_mixed_colors_to_multicolor():
    assert resolve_gmc_color("One pair of mixed colors [10a antibacterial]") == "Multicolor"
    assert resolve_gmc_color("mixed colours") == "Multicolor"


def test_multicolor_synonyms_without_named_hue():
    assert resolve_gmc_color("Colorful") == "Multicolor"
    assert resolve_gmc_color("COLOURFUL") == "Multicolor"
    assert resolve_gmc_color("花色") == "Multicolor"
    assert resolve_gmc_color("multi-color") == "Multicolor"


def test_named_hue_wins_over_multicolor_synonym():
    assert resolve_gmc_color("Colorful Black") == "Black"
    assert resolve_gmc_color("Black") == "Black"


def test_color_word_alone_is_not_multicolor_synonym():
    from adfeed.attribute_normalizer import _canonical_color_token

    assert _canonical_color_token("color") == ""
    assert _canonical_color_token("Colorful") == "Multicolor"


def test_normal_color_passthrough():
    assert resolve_gmc_color("Apricot") == "Apricot"
    assert resolve_gmc_color("Navy Blue Flower") == "Navy Blue"


def test_pattern_extracted_not_merged_into_color():
    assert resolve_gmc_color("Black Flower") == "Black"
    assert extract_pattern_from_color_raw("Black Flower", hue="Black") in ("Floral", "Flower")
    a_c, a_p = resolve_gmc_color_and_pattern("Black Flower")
    b_c, b_p = resolve_gmc_color_and_pattern("Black with white stripes")
    assert a_c == "Black" and b_c == "Black"
    assert a_p != b_p


def test_white_stripe_variants_share_hue_distinct_pattern():
    rows = [
        resolve_gmc_color_and_pattern("White background with black stripes"),
        resolve_gmc_color_and_pattern("White background with curved stripes"),
        resolve_gmc_color_and_pattern("White vertical stripe"),
    ]
    assert all(c == "White" for c, _ in rows)
    patterns = [p for _, p in rows]
    assert len(set(patterns)) == 3
