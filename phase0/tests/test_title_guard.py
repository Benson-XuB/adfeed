"""Title: category discipline only; append this-row color+size once (field contract)."""
import re

from adfeed.title_guard import (
    allows_tummy_control,
    polish_feed_title,
    sanitize_shopping_title,
)


def test_tummy_banned_on_outerwear():
    assert not allows_tummy_control("Apparel > Clothing > Outerwear > Vests")
    assert not allows_tummy_control("Apparel > Clothing > Outerwear > Coats & Jackets")
    assert allows_tummy_control("Apparel > Clothing > Dresses")
    assert allows_tummy_control("Apparel > Clothing > Pants")


def test_sanitize_strips_tummy_on_vest():
    raw = "eprolo Women Vest Tummy Control for Summer Friday Brunch Sizes S-XXL, Black"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Outerwear > Vests",
    )
    assert "tummy" not in out.lower()
    assert "brunch" not in out.lower()
    assert "vest" in out.lower()


def test_sanitize_strips_brunch_without_orphan_for():
    raw = "eprolo Women Lace V-Neck Long Sleeve Top for Weekend Brunch & Office S-XXL"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Shirts & Tops",
    )
    assert "brunch" not in out.lower()
    assert "for &" not in out.lower()
    assert "top" in out.lower()


def test_fix_for_regular_fit_remnant():
    """Fit Type is dump noise — strip, do not keep as selling point."""
    raw = "eprolo Women High Waist Jeans Blue for Regular fit, zipper fly, Denim"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Pants",
    )
    assert "for Regular" not in out
    assert "regular fit" not in out.lower()
    assert "zipper" not in out.lower()
    assert "Denim" in out or "denim" in out.lower()
    assert "High Waist" in out or "Jeans" in out


def test_fix_for_long_sleeve_remnant():
    raw = "eprolo Women Short Jacket Brown Slim Fit for Long Sleeve V-Neck PU"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert not re.search(r"\bfor\s+Long\s+Sleeve\b", out, re.I)
    assert re.search(r"Long\s+Sleeve", out, re.I)
    # Slim Fit / PU dump stripped; V-Neck kept
    assert "slim fit" not in out.lower()
    assert re.search(r"\bPU\b", out) is None or "PU" not in out
    assert re.search(r"V-?Neck", out, re.I)


def test_sanitize_strips_closure_bullets_and_polyester_wall():
    raw = (
        "Women Dress Sleeveless Striped Polyester for Beach Day "
        "• Fitted Fit • Pullover Closure | Nylon-Spandex Blend"
    )
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    assert "•" not in out
    assert "|" not in out
    assert "closure" not in out.lower()
    assert "fitted fit" not in out.lower()
    assert "polyester" not in out.lower()
    assert "nylon" not in out.lower()
    assert "spandex" not in out.lower()
    assert "Dress" in out
    assert "Sleeveless" in out


def test_sanitize_keeps_searchable_denim_and_floral():
    raw = "Women Floral Print Denim Jacket for Everyday Casual"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert "Floral" in out
    assert "Denim" in out
    assert "Jacket" in out


def test_sanitize_keeps_tummy_on_dress():
    raw = "Women Printed Dress Tummy Control for Summer Wedding Guest"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    assert "tummy control" in out.lower()
    assert "wedding" in out.lower()


def test_polish_is_skeleton_plus_color_and_size_once():
    """Field contract: no Plus Size / material wall — color+size once; pattern only if passed."""
    base = "Women Printed Dress Sleeveless for Summer Wedding Guest S-5XL"
    out = polish_feed_title(
        base, color="Apricot", size="L",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    compact = re.sub(r"[\s–—]", "", out.upper())
    assert "S-5XL" not in compact
    assert "Apricot" in out
    assert re.search(r"\bSize\s+L\b", out, re.I)
    assert "Plus Size" not in out
    assert out.count("Apricot") == 1


def test_polish_aligns_pattern_for_any_product_type():
    """High-quality P0: this-row searchable pattern for ALL types, not dress-only."""
    dress = polish_feed_title(
        "Women's Striped Sleeveless Dress",
        color="Black", size="L", pattern="Floral",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    assert "Floral" in dress
    assert "Striped" not in dress  # this-row Floral replaces skeleton Stripe family
    assert "Black" in dress and "Size L" in dress

    jacket = polish_feed_title(
        "Women's V-Neck Long Sleeve Jacket Casual",
        color="Brown", size="L", pattern="Style 1",
        gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert "Style" not in jacket  # never Style N
    assert "Brown" in jacket

    top = polish_feed_title(
        "Women's Lace V-Neck Long Sleeve Top",
        color="White", size="M", pattern="Polka Dot",
        gpc_path="Apparel & Accessories > Clothing > Shirts & Tops",
    )
    assert "Polka Dot" in top
    assert "White" in top and "Size M" in top


def test_polish_aligns_stripe_subtypes():
    base = "Women's Striped Sleeveless Dress"
    v = polish_feed_title(base, color="White", size="L", pattern="Vertical Stripe")
    c = polish_feed_title(base, color="White", size="L", pattern="Curved Stripe")
    s = polish_feed_title(base, color="White", size="L", pattern="Stripe")
    assert "Vertical Stripe" in v
    assert "Curved Stripe" in c
    assert "Striped" in s or "Stripe" in s
    assert v != c and c != s


def test_polish_differentiates_by_this_row_attrs_not_mid_insert():
    base = "Women Dress Sleeveless for Beach Day"
    a = polish_feed_title(
        base, color="Apricot", size="5XL",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    b = polish_feed_title(
        base, color="Black", size="M",
        gpc_path="Apparel & Accessories > Clothing > Dresses",
    )
    assert a != b
    assert "Apricot" in a and "Black" in b
    assert "Size 5XL" in a
    assert "Size M" in b


def test_sanitize_strips_llm_blend_debris():
    raw = "Women's High Waist Denim Jeans Cotton- blend. ."
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Pants",
    )
    assert "blend" not in out.lower()
    assert "Denim" in out
    assert "Jeans" in out
    assert not out.rstrip().endswith(".")


def test_polish_strips_sizes_list_then_pins_one():
    base = "Women Jacket PU Slim Fit for Streetwear Casual Brown, Sizes S M L"
    out = polish_feed_title(
        base, color="Brown", size="L",
        gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert not re.search(r"Sizes?\s+S\s+M\s+L", out, re.I)
    assert re.search(r"\bSize\s+L\b", out, re.I)


def test_sanitize_does_not_inject_casual_on_jacket():
    """Field contract: sanitize strips junk — must not invent Casual after Jacket."""
    raw = "Women's Lace-Up Belted Leather Jacket for Summer Friday Brunch"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert "brunch" not in out.lower()
    assert "summer friday" not in out.lower()
    assert "Jacket" in out
    assert not re.search(r"\bCasual\b", out, re.I)
    assert "Lace-Up" in out or "Leather" in out


def test_sanitize_strips_weak_everyday_casual_filler():
    """Weak scene filler after type — drop; keep real attrs (Lace, Patchwork)."""
    raw = "Women's Lace Patchwork Vest for Everyday Casual"
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Outerwear > Vests",
    )
    assert "Lace" in out
    assert "Patchwork" in out or "Vest" in out
    assert "everyday" not in out.lower()
    assert not re.search(r"\bCasual\b", out, re.I)


def test_sanitize_strips_post_type_marketing_fluff():
    """LLM feature walls after product type — strip for all apparel, not socks-only."""
    raw = (
        "Women's Cotton Invisible Boat Socks Anti-slip Breathable "
        "Sweat-absorbent Antibacterial"
    )
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > Underwear & Socks > Socks",
    )
    assert "Anti-slip" not in out
    assert "Antibacterial" not in out
    assert "Sweat-absorbent" not in out
    assert "Boat Socks" in out or "Socks" in out
    assert "Cotton" in out


def test_sanitize_strips_color_blend_debris_on_jumpsuit():
    raw = "Women's Sleeveless Spliced Jumpsuit Black. - blend."
    out = sanitize_shopping_title(
        raw, gpc_path="Apparel & Accessories > Clothing > One-Pieces > Jumpsuits",
    )
    assert "blend" not in out.lower()
    assert "Black." not in out
    assert " Black" not in out.split("Jumpsuit")[-1]
    assert "Jumpsuit" in out


def test_polish_replaces_stale_size_in_feed_title_override():
    """Merchant/DB feed_title with wrong Size L + row size M → one Size M only."""
    override = "Northvale Women's High Waist Denim Jeans, Blue, X Size L"
    out = polish_feed_title(
        override,
        color="Blue",
        size="M",
        gpc_path="Apparel & Accessories > Clothing > Pants",
    )
    assert "X Size" not in out
    assert "Size L" not in out
    assert re.search(r"\bSize\s+M\b", out, re.I)
    assert out.count("Blue") == 1


def test_polish_jacket_keeps_two_real_attrs_without_casual_pad():
    out = polish_feed_title(
        "Women's Lace V-Neck Long Sleeve Jacket Casual",
        color="Black",
        size="L",
        gpc_path="Apparel & Accessories > Clothing > Outerwear > Coats & Jackets",
    )
    assert "Lace" in out
    assert re.search(r"V-?Neck", out, re.I)
    assert "Black" in out and "Size L" in out
    assert not re.search(r"\bCasual\b", out, re.I)
    assert "summer" not in out.lower()
    assert "vintage" not in out.lower()
    assert "elegant" not in out.lower()
