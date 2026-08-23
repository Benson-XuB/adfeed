"""Shopify Markets contextual pricing fetch (mocked HTTP)."""
from unittest.mock import MagicMock, patch

from adfeed.shopify_markets import fetch_contextual_pricing, _to_variant_gid


def test_to_variant_gid():
    assert _to_variant_gid("41575567491130") == "gid://shopify/ProductVariant/41575567491130"
    assert (
        _to_variant_gid("gid://shopify/ProductVariant/41575567491130")
        == "gid://shopify/ProductVariant/41575567491130"
    )
    assert _to_variant_gid("hex-sku") is None


def test_fetch_contextual_pricing_maps_amounts():
    payload = {
        "data": {
            "nodes": [
                {
                    "id": "gid://shopify/ProductVariant/111",
                    "contextualPricing": {
                        "price": {"amount": "27.85", "currencyCode": "USD"},
                    },
                },
                {
                    "id": "gid://shopify/ProductVariant/222",
                    "contextualPricing": {
                        "price": {"amount": "19.00", "currencyCode": "USD"},
                    },
                },
                None,
            ]
        }
    }
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = payload

    with patch("adfeed.shopify_markets.requests.post", return_value=mock_resp) as post:
        out = fetch_contextual_pricing(
            "demo.myshopify.com",
            "tok",
            ["111", "gid://shopify/ProductVariant/222"],
            "US",
        )
    assert out is not None
    assert out["111"]["amount"] == 27.85
    assert out["111"]["currency"] == "USD"
    assert out["222"]["currency"] == "USD"
    args = post.call_args
    assert args.kwargs["json"]["variables"]["country"] == "US"


def test_fetch_returns_none_on_401():
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "unauthorized"
    with patch("adfeed.shopify_markets.requests.post", return_value=mock_resp):
        assert (
            fetch_contextual_pricing("demo.myshopify.com", "tok", ["111"], "US") is None
        )


def test_fetch_empty_ids_returns_none():
    assert fetch_contextual_pricing("demo.myshopify.com", "tok", [], "US") is None
    assert fetch_contextual_pricing("demo.myshopify.com", "tok", ["abc"], "US") is None
