"""Resolve which feed countries are GREEN for a shop (dropdown source).

Scheme A + partial B:
1. Shop-currency fast path — no contextualPricing call when expected == shop currency.
2. With token, narrow candidates via Shopify Markets regions.
3. Probe remaining candidates with contextualPricing + preflight_country.
4. Return only GREEN countries (FEED_COUNTRY_ORDER).
"""
from __future__ import annotations

import logging
from typing import Optional

from .market_pricing import (
    FEED_COUNTRY_ORDER,
    PreflightStatus,
    countries_for_currency,
    expected_currency_for_country,
    list_feed_countries,
    normalize_country_code,
    preflight_country,
)
from .shopify_markets import fetch_contextual_pricing, fetch_market_country_codes

logger = logging.getLogger(__name__)

_SUPPORTED = {code for code, _ in list_feed_countries()}


def _sample_variant_ids(store_id: str, limit: int = 5) -> list[str]:
    from . import store_db

    vids: list[str] = []
    for p in store_db.get_store_products(store_id)[:12]:
        for v in store_db.get_product_variants(p.id):
            vid = (v.shopify_variant_id or "").strip()
            if vid.isdigit():
                vids.append(vid)
            if len(vids) >= limit:
                break
        if len(vids) >= limit:
            break
    return vids


def _candidate_countries(
    shop_currency: str,
    market_countries: Optional[set[str]],
) -> list[str]:
    """Countries to probe, in merchant chip order."""
    shop_ccy = (shop_currency or "USD").strip().upper()
    ccy_fallback = set(countries_for_currency(shop_ccy)) & _SUPPORTED

    if market_countries is not None:
        narrowed = market_countries & _SUPPORTED
        candidates = narrowed or ccy_fallback
    else:
        candidates = ccy_fallback or _SUPPORTED

    if not candidates:
        candidates = {"US"} & _SUPPORTED

    return [c for c in FEED_COUNTRY_ORDER if c in candidates]


def list_compatible_markets(
    *,
    store_id: str,
    shop_domain: str,
    access_token: Optional[str],
    shop_currency: str,
) -> dict:
    shop_ccy = (shop_currency or "USD").strip().upper()
    market_countries: Optional[set[str]] = None
    markets_source = "shop_currency"

    if access_token and shop_domain:
        raw = fetch_market_country_codes(shop_domain, access_token)
        if raw is not None:
            market_countries = raw
            markets_source = "shopify_markets"

    candidates = _candidate_countries(shop_ccy, market_countries)
    vids = _sample_variant_ids(store_id) if access_token and shop_domain else []

    ready: list[str] = []
    for country in candidates:
        expected = expected_currency_for_country(country)
        if shop_ccy == expected:
            pf = preflight_country(shop_currency=shop_ccy, country=country)
            if pf.status == PreflightStatus.GREEN:
                ready.append(country)
            continue

        if not access_token or not shop_domain or not vids:
            continue

        fetched = fetch_contextual_pricing(
            shop_domain, access_token, vids, country,
        )
        sample = None
        if fetched:
            first = next(iter(fetched.values()))
            sample = {country: first}
        pf = preflight_country(
            shop_currency=shop_ccy,
            country=country,
            sample_presentment=sample,
        )
        if pf.status == PreflightStatus.GREEN:
            ready.append(country)

    default_country = ready[0] if ready else "US"
    if default_country not in ready and ready:
        default_country = ready[0]

    return {
        "ready": ready,
        "shop_currency": shop_ccy,
        "markets_source": markets_source,
        "candidate_countries": candidates,
        "default_country": default_country,
    }
