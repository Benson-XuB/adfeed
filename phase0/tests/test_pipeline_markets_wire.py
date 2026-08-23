"""Pipeline attaches Markets presentment onto variants when fetch succeeds."""
from unittest.mock import MagicMock


def test_presentment_attached_when_markets_returns_usd(monkeypatch):
    """CNY shop + US presentment → resolve uses Markets USD (contract for pipeline)."""
    from adfeed.market_pricing import resolve_market_price, preflight_country, PreflightStatus

    pf = preflight_country(
        shop_currency="CNY",
        country="US",
        sample_presentment={"US": {"amount": 27.85, "currency": "USD"}},
    )
    assert pf.status == PreflightStatus.GREEN

    priced = resolve_market_price(
        amount=199.0,
        shop_currency="CNY",
        country="US",
        presentment={"US": {"amount": 27.85, "currency": "USD"}},
    )
    assert priced.ok
    assert priced.currency == "USD"
    assert priced.amount == 27.85
    assert priced.source == "markets"


def test_fetch_wired_shape_matches_pipeline_lookup():
    """Numeric id key is what pipeline uses: pricing_by_variant.get(vid)."""
    from adfeed.shopify_markets import fetch_contextual_pricing
    from unittest.mock import patch, MagicMock

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "data": {
            "nodes": [{
                "id": "gid://shopify/ProductVariant/41575567491130",
                "contextualPricing": {
                    "price": {"amount": "12.00", "currencyCode": "USD"},
                },
            }]
        }
    }
    with patch("adfeed.shopify_markets.requests.post", return_value=mock_resp):
        out = fetch_contextual_pricing(
            "demo.myshopify.com", "t", ["41575567491130"], "US",
        )
    assert out["41575567491130"]["amount"] == 12.0
    vd = {"shopify_variant_id": "41575567491130"}
    entry = out.get(vd["shopify_variant_id"])
    assert entry["currency"] == "USD"
