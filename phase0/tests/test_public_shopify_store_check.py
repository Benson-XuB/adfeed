"""Tests for public Shopify storefront products.json checker."""

from adfeed.public_tools.shopify_store_check import (
    analyze_products_payload,
    normalize_shop_domain,
)


def test_normalize_shop_domain():
    assert normalize_shop_domain("https://Foo-Bar.myshopify.com/") == "foo-bar.myshopify.com"
    assert normalize_shop_domain("foo-bar.myshopify.com") == "foo-bar.myshopify.com"
    assert normalize_shop_domain("https://example.com") is None


def test_analyze_products_flags_dirty_vendor_and_title_noise():
    payload = {
        "products": [
            {
                "id": 1,
                "title": "Women Dress New Arrival Free Shipping",
                "vendor": "eprolo",
                "image": None,
                "images": [],
                "variants": [
                    {"title": "Default Title", "option1": None, "option2": None, "price": "19.99"}
                ],
                "options": [{"name": "Title", "values": ["Default Title"]}],
            },
            {
                "id": 2,
                "title": "Women's Linen Midi Dress Blue",
                "vendor": "My Brand",
                "image": {"src": "https://cdn.example/a.jpg"},
                "images": [{"src": "https://cdn.example/a.jpg"}],
                "variants": [
                    {"title": "Blue / M", "option1": "Blue", "option2": "M", "price": "29.00"}
                ],
                "options": [
                    {"name": "Color", "values": ["Blue"]},
                    {"name": "Size", "values": ["M"]},
                ],
            },
        ]
    }
    r = analyze_products_payload(payload, shop="demo.myshopify.com")
    assert r["ok"] is True
    assert r["products_checked"] == 2
    assert r["issue_total"] >= 1
    codes = {b["code"] for b in r["buckets"]}
    assert "dirty_vendor" in codes or "noisy_or_long_title" in codes
    assert "missing_image" in codes
