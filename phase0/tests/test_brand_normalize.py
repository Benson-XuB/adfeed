"""Brand resolution: no silent eprolo (field contract)."""
from adfeed.pipeline import _normalize_brand, _resolve_store_brand, _store_brand_fallback


class _Store:
    def __init__(self, shop_name="", default_brand="", site_url=""):
        self.shop_name = shop_name
        self.default_brand = default_brand
        self.site_url = site_url


def test_no_silent_eprolo_when_shop_readable():
    brand, status = _normalize_brand("eprolo", "Acme Apparel", None)
    assert brand == "Acme Apparel"
    assert status == "replaced"


def test_missing_when_no_store_brand_and_placeholder_product():
    brand, status = _normalize_brand("eprolo", "qx2kd5-s7", None)
    assert brand == ""
    assert status == "missing"


def test_confirmed_default_brand_wins_even_if_eprolo():
    brand, status = _normalize_brand("OEM Factory", "qx2kd5-s7", "eprolo")
    assert brand == "eprolo"
    assert status == "replaced"


def test_store_brand_fallback_prefers_default():
    assert _store_brand_fallback("Shop Name", "My Label") == "My Label"
    assert _store_brand_fallback("Shop Name", None) == "Shop Name"


def test_resolve_store_brand_uses_site_label():
    s = _Store(shop_name="qx2kd5-s7", site_url="https://www.acmelabel.com")
    assert _resolve_store_brand(s) == "acmelabel"
