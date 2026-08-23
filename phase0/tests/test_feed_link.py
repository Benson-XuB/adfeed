"""Feed link builder: pin currency + variant for GMC crawl alignment."""
from adfeed.feed_link import build_product_link, resolve_shopify_variant_id


def test_pins_currency_and_variant():
    url = build_product_link(
        "https://shop.example.com/products/dress",
        variant_id="123",
        currency="USD",
    )
    assert url.startswith("https://shop.example.com/products/dress?")
    assert "variant=123" in url
    assert "currency=USD" in url


def test_merges_existing_query_without_double_question():
    url = build_product_link(
        "https://shop.example.com/products/dress?utm_source=x",
        currency="EUR",
    )
    assert url.count("?") == 1
    assert "utm_source=x" in url
    assert "currency=EUR" in url


def test_overrides_existing_currency_param():
    url = build_product_link(
        "https://shop.example.com/products/dress?currency=CNY",
        currency="USD",
    )
    assert "currency=USD" in url
    assert "currency=CNY" not in url


def test_empty_base_returns_empty():
    assert build_product_link("", currency="USD") == ""


def test_resolve_accepts_numeric_shopify_variant_id():
    assert resolve_shopify_variant_id("41575567491130") == "41575567491130"
    assert resolve_shopify_variant_id(41575567491130) == "41575567491130"


def test_resolve_rejects_internal_hex_sku():
    """Never use AdFeed internal SKU as ?variant= — wastes ad spend on wrong SKU."""
    assert resolve_shopify_variant_id("A8842A68B5FF40CB8B382327EEEF6C40") is None
    assert resolve_shopify_variant_id("sku-black-m") is None
    assert resolve_shopify_variant_id("") is None
    assert resolve_shopify_variant_id(None) is None


def test_resolve_prefers_shopify_field_over_sku_fallback():
    assert (
        resolve_shopify_variant_id(
            None,
            candidates=["A8842A68B5FF40CB8B382327EEEF6C40", "41575567491130"],
        )
        == "41575567491130"
    )
    # Only fake candidates → None (do not invent)
    assert (
        resolve_shopify_variant_id(
            None,
            candidates=["A8842A68B5FF40CB8B382327EEEF6C40"],
        )
        is None
    )
