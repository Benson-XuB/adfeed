"""GPC: apparel strong-type aliases and adjective hijack guards."""
from adfeed.gpc_matcher import match, load_taxonomy, _detect_product_types


def setup_module():
    load_taxonomy()


CASES = [
    ("High waisted zipper leg tied jeans for women", "204", "Pants"),
    ("Printed camisole dress", "2271", "Dresses"),
    ("Pure Cotton Boat Socks for Women", "209", "Socks"),
    ("Slanted shoulder hollow tight jumpsuit for women", "5250", "Jumpsuits"),
    ("Slanted shoulder metal buckle lace patchwork irregular loose vest for women", "1831", "Vests"),
    ("Sleeveless slim fit A-line jacket", "5598", "Jackets"),
    ("Strap and slit long sleeved V-neck lace top", "212", "Shirts & Tops"),
    ("Strap up short long sleeved jacket", "5598", "Jackets"),
    ("Wave point hanging neck sleeveless top", "212", "Shirts & Tops"),
]


def test_detect_jacket_not_shorts():
    assert "jacket" in _detect_product_types("Strap up short long sleeved jacket")
    assert "shorts" not in _detect_product_types("Strap up short long sleeved jacket")


def test_detect_jumpsuit_and_top():
    assert "jumpsuit" in _detect_product_types("hollow tight jumpsuit for women")
    assert "top" in _detect_product_types("sleeveless top")
    assert "vest" in _detect_product_types("loose vest for women")


def test_store_titles_match_expected_gpc():
    for title, code, path_hint in CASES:
        r = match(title=title, category="", material="")
        assert r["gpc_code"] == code, (
            f"{title!r} → {r['gpc_code']} {r['gpc_path']} (want {code} ~{path_hint})"
        )
        assert path_hint.lower() in (r.get("gpc_path") or "").lower()
