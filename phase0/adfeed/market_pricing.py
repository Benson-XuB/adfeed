"""Resolve feed price/currency — no FX submit path.

Rule: Feed country currency must match buyer-visible shop/presentment currency.
Guidance is flat: if you target X, make the storefront show X's currency.
Default product market in App UI: US (USD).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Optional


COUNTRY_CURRENCY = {
    # Americas
    "US": "USD",
    "CA": "CAD",
    # Europe — eurozone
    "DE": "EUR",
    "FR": "EUR",
    "ES": "EUR",
    "IT": "EUR",
    "NL": "EUR",
    "BE": "EUR",
    "AT": "EUR",
    "IE": "EUR",
    "PT": "EUR",
    "FI": "EUR",
    "GR": "EUR",
    "LU": "EUR",
    # Europe — other developed
    "GB": "GBP",
    "UK": "GBP",
    "SE": "SEK",
    "NO": "NOK",
    "DK": "DKK",
    "CH": "CHF",
    "PL": "PLN",
    # Oceania
    "AU": "AUD",
    "NZ": "NZD",
    # East & Southeast Asia
    "JP": "JPY",
    "KR": "KRW",
    "SG": "SGD",
    "HK": "HKD",
    "TW": "TWD",
    # Gulf
    "QA": "QAR",
    "AE": "AED",
}

# Merchant-facing chip order in App UI (ISO 3166-1 alpha-2).
FEED_COUNTRY_ORDER = [
    "US",
    "CA",
    "GB",
    "DE",
    "FR",
    "ES",
    "IT",
    "NL",
    "BE",
    "AT",
    "IE",
    "PT",
    "FI",
    "SE",
    "NO",
    "DK",
    "CH",
    "PL",
    "AU",
    "NZ",
    "JP",
    "KR",
    "SG",
    "HK",
    "TW",
    "QA",
    "AE",
]


def normalize_country_code(country: str) -> str:
    cu = (country or "US").strip().upper()
    if cu == "UK":
        return "GB"
    return cu


def list_feed_countries() -> list[tuple[str, str]]:
    """Return (country, currency) pairs for supported developed-market feeds."""
    out: list[tuple[str, str]] = []
    for code in FEED_COUNTRY_ORDER:
        ccy = COUNTRY_CURRENCY.get(code)
        if ccy:
            out.append((code, ccy))
    return out


class PreflightStatus(str, Enum):
    GREEN = "green"
    RED = "red"


@dataclass(frozen=True)
class ResolvedPrice:
    ok: bool
    amount: float = 0.0
    currency: str = ""
    source: str = ""  # shop | markets
    code: str = ""
    message: str = ""


@dataclass(frozen=True)
class PreflightResult:
    status: PreflightStatus
    country: str
    expected_currency: str
    shop_currency: str
    code: str = ""
    message: str = ""


def expected_currency_for_country(country: str) -> str:
    cu = normalize_country_code(country)
    return COUNTRY_CURRENCY.get(cu, "USD")


def countries_for_currency(currency: str) -> list[str]:
    ccy = (currency or "").strip().upper()
    return [c for c, cur in COUNTRY_CURRENCY.items() if cur == ccy and c != "UK"]


def mismatch_guidance(shop_currency: str, country: str, expected: str) -> str:
    """Flat tip: target market requires matching storefront currency — change it in Shopify."""
    shop_ccy = (shop_currency or "").strip().upper() or "USD"
    cu = (country or "").strip().upper()
    return (
        f"You selected {cu}; the feed needs {expected}, but the shop presentment currency is {shop_ccy}. "
        f"In Shopify, set buyer-facing prices for that market to {expected} "
        f"(e.g. switch primary currency or enable {expected} on that market page), then regenerate. "
        f"The app will not auto-convert FX."
    )


def _presentment_entry(
    presentment: Optional[Mapping[str, Any]],
    country: str,
) -> Optional[dict]:
    if not presentment:
        return None
    cu = country.strip().upper()
    entry = presentment.get(cu) or presentment.get(cu.lower())
    if not isinstance(entry, dict):
        return None
    return entry


def resolve_market_price(
    amount: float,
    shop_currency: str,
    country: str,
    presentment: Optional[Mapping[str, Any]] = None,
) -> ResolvedPrice:
    """Pick buyer-visible price for ``country``. Never invent FX for submit."""
    cu = normalize_country_code(country)
    expected = expected_currency_for_country(cu)
    shop_ccy = (shop_currency or "").strip().upper() or "USD"

    entry = _presentment_entry(presentment, cu)
    if entry:
        try:
            p_amount = float(entry.get("amount", 0) or 0)
        except (TypeError, ValueError):
            p_amount = 0.0
        p_ccy = str(entry.get("currency", "") or "").strip().upper()
        if p_amount > 0 and p_ccy:
            if p_ccy != expected:
                return ResolvedPrice(
                    ok=False,
                    code="CURRENCY_MISMATCH",
                    message=(
                        f"You selected {cu}, which needs {expected}, but presentment currency read as {p_ccy}. "
                        f"Change that market display to {expected} in Shopify, then regenerate."
                    ),
                )
            return ResolvedPrice(
                ok=True,
                amount=round(p_amount, 2),
                currency=p_ccy,
                source="markets",
            )

    if shop_ccy == expected:
        try:
            amt = float(amount or 0)
        except (TypeError, ValueError):
            amt = 0.0
        if amt <= 0:
            return ResolvedPrice(
                ok=False,
                code="ZERO_PRICE",
                message=f"Invalid price: {amount}",
            )
        return ResolvedPrice(
            ok=True,
            amount=round(amt, 2),
            currency=shop_ccy,
            source="shop",
        )

    return ResolvedPrice(
        ok=False,
        code="CURRENCY_MISMATCH",
        message=mismatch_guidance(shop_ccy, cu, expected),
    )


def preflight_country(
    shop_currency: str,
    country: str,
    sample_presentment: Optional[Mapping[str, Any]] = None,
) -> PreflightResult:
    cu = normalize_country_code(country)
    expected = expected_currency_for_country(cu)
    shop_ccy = (shop_currency or "").strip().upper() or "USD"

    probe = resolve_market_price(
        amount=1.0,
        shop_currency=shop_ccy,
        country=cu,
        presentment=sample_presentment,
    )
    if probe.ok:
        msg = (
            f"{cu} matches presentment currency {probe.currency}. "
            f"Links will include ?currency={probe.currency}."
        )
        return PreflightResult(
            status=PreflightStatus.GREEN,
            country=cu,
            expected_currency=expected,
            shop_currency=shop_ccy,
            message=msg,
        )

    return PreflightResult(
        status=PreflightStatus.RED,
        country=cu,
        expected_currency=expected,
        shop_currency=shop_ccy,
        code=probe.code or "CURRENCY_MISMATCH",
        message=probe.message,
    )
