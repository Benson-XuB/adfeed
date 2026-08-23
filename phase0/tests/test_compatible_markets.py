"""Compatible market resolution (shop currency fast path + Markets narrow + preflight)."""
from unittest.mock import patch

from adfeed.compatible_markets import list_compatible_markets


def test_usd_shop_markets_us_only_fast_path():
    with patch("adfeed.compatible_markets.fetch_market_country_codes", return_value={"US"}):
        out = list_compatible_markets(
            store_id="s1",
            shop_domain="shop.myshopify.com",
            access_token="tok",
            shop_currency="USD",
        )
    assert out["ready"] == ["US"]
    assert out["markets_source"] == "shopify_markets"
    assert out["default_country"] == "US"


def test_eur_shop_markets_de_only_not_all_eurozone():
    with patch("adfeed.compatible_markets.fetch_market_country_codes", return_value={"DE"}):
        out = list_compatible_markets(
            store_id="s1",
            shop_domain="shop.myshopify.com",
            access_token="tok",
            shop_currency="EUR",
        )
    assert out["ready"] == ["DE"]
    assert "FR" not in out["ready"]


def test_cny_shop_us_market_needs_contextual_pricing():
    presentment = {"US": {"amount": 29.0, "currency": "USD"}}

    def fake_pricing(_shop, _tok, _vids, country):
        if country == "US":
            return {"1": presentment["US"]}
        return None

    with (
        patch("adfeed.compatible_markets.fetch_market_country_codes", return_value={"US"}),
        patch("adfeed.compatible_markets._sample_variant_ids", return_value=["1"]),
        patch("adfeed.compatible_markets.fetch_contextual_pricing", side_effect=fake_pricing),
    ):
        out = list_compatible_markets(
            store_id="s1",
            shop_domain="shop.myshopify.com",
            access_token="tok",
            shop_currency="CNY",
        )
    assert out["ready"] == ["US"]


def test_cny_shop_us_market_red_without_presentment():
    with (
        patch("adfeed.compatible_markets.fetch_market_country_codes", return_value={"US"}),
        patch("adfeed.compatible_markets._sample_variant_ids", return_value=["1"]),
        patch("adfeed.compatible_markets.fetch_contextual_pricing", return_value=None),
    ):
        out = list_compatible_markets(
            store_id="s1",
            shop_domain="shop.myshopify.com",
            access_token="tok",
            shop_currency="CNY",
        )
    assert out["ready"] == []


def test_no_token_falls_back_to_shop_currency_countries():
    with patch("adfeed.compatible_markets.fetch_market_country_codes") as m:
        out = list_compatible_markets(
            store_id="s1",
            shop_domain="shop.myshopify.com",
            access_token=None,
            shop_currency="GBP",
        )
    m.assert_not_called()
    assert "GB" in out["ready"]
    assert out["markets_source"] == "shop_currency"
