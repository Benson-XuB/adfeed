"""Market presentment resolve + generate preflight (no internal FX)."""
from adfeed.market_pricing import (
    PreflightStatus,
    expected_currency_for_country,
    preflight_country,
    resolve_market_price,
)


def test_expected_currency_developed_markets():
    assert expected_currency_for_country("GB") == "GBP"
    assert expected_currency_for_country("JP") == "JPY"
    assert expected_currency_for_country("KR") == "KRW"
    assert expected_currency_for_country("SG") == "SGD"
    assert expected_currency_for_country("QA") == "QAR"
    assert expected_currency_for_country("UK") == "GBP"


def test_list_feed_countries_includes_new_markets():
    from adfeed.market_pricing import list_feed_countries

    codes = [c for c, _ in list_feed_countries()]
    assert "US" in codes
    assert "GB" in codes
    assert "JP" in codes
    assert "KR" in codes
    assert "SG" in codes
    assert "QA" in codes
    assert len(codes) >= 25


def test_expected_currency():
    assert expected_currency_for_country("US") == "USD"
    assert expected_currency_for_country("DE") == "EUR"
    assert expected_currency_for_country("fr") == "EUR"


def test_resolve_same_shop_currency_uses_amount_no_fx():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="USD",
        country="US",
        presentment=None,
    )
    assert r.ok
    assert r.amount == 199.0
    assert r.currency == "USD"
    assert r.source == "shop"


def test_resolve_presentment_overrides_shop_cny_for_us():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="CNY",
        country="US",
        presentment={"US": {"amount": 27.85, "currency": "USD"}},
    )
    assert r.ok
    assert r.amount == 27.85
    assert r.currency == "USD"
    assert r.source == "markets"


def test_resolve_mismatch_without_presentment_fails():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="CNY",
        country="US",
        presentment=None,
    )
    assert not r.ok
    assert r.code == "CURRENCY_MISMATCH"


def test_preflight_blocks_cny_for_us():
    pf = preflight_country(shop_currency="CNY", country="US", sample_presentment=None)
    assert pf.status == PreflightStatus.RED
    assert pf.code == "CURRENCY_MISMATCH"
    assert "US" in pf.message and "USD" in pf.message
    assert "Shopify" in pf.message
    assert "入门" not in pf.message and "进阶" not in pf.message


def test_mismatch_guidance_is_flat():
    from adfeed.market_pricing import mismatch_guidance
    msg = mismatch_guidance("CNY", "US", "USD")
    assert "入门" not in msg and "进阶" not in msg
    assert "convert" in msg.lower() or "currency" in msg.lower()
    assert "USD" in msg


def test_countries_for_currency_usd():
    from adfeed.market_pricing import countries_for_currency
    assert "US" in countries_for_currency("USD")
    assert countries_for_currency("CNY") == []


def test_preflight_green_when_currencies_align():
    pf = preflight_country(shop_currency="USD", country="US", sample_presentment=None)
    assert pf.status == PreflightStatus.GREEN


def test_preflight_green_with_presentment_despite_shop_cny():
    pf = preflight_country(
        shop_currency="CNY",
        country="US",
        sample_presentment={"US": {"amount": 10.0, "currency": "USD"}},
    )
    assert pf.status == PreflightStatus.GREEN
