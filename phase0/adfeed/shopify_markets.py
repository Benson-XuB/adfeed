"""Shopify Markets / contextual pricing for feed presentment.

Fetches buyer-visible price+currency per variant for a country via Admin
GraphQL ``contextualPricing``. Returns None when token/API unavailable so
preflight can fall back to shop currency rules.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional

import requests

from .config import SHOPIFY_API_VERSION

logger = logging.getLogger(__name__)

_VARIANT_GID_RE = re.compile(r"gid://shopify/ProductVariant/(\d+)", re.I)
_BATCH = 50


def _to_variant_gid(raw: str) -> Optional[str]:
    s = str(raw or "").strip()
    if not s:
        return None
    m = _VARIANT_GID_RE.match(s)
    if m:
        return f"gid://shopify/ProductVariant/{m.group(1)}"
    if s.isdigit():
        return f"gid://shopify/ProductVariant/{s}"
    return None


def _numeric_id(gid_or_num: str) -> str:
    m = _VARIANT_GID_RE.match(str(gid_or_num or ""))
    if m:
        return m.group(1)
    return str(gid_or_num or "").strip()


def fetch_contextual_pricing(
    shop_domain: str,
    access_token: str,
    variant_gids: list[str],
    country_code: str,
) -> Optional[dict[str, dict[str, Any]]]:
    """Return map variant_id (numeric str) → {amount, currency} for country.

    Keys are numeric Shopify variant ids (and also GID strings when present)
    so callers can look up either form. Returns None if request cannot run
    or yields no usable prices.
    """
    shop = (shop_domain or "").replace("https://", "").replace("http://", "").strip().lower()
    if shop.endswith("/"):
        shop = shop[:-1]
    if shop and not shop.endswith(".myshopify.com") and "." not in shop:
        shop = f"{shop}.myshopify.com"
    if not shop or not access_token:
        return None

    country = (country_code or "US").strip().upper()
    if country == "UK":
        country = "GB"

    gids: list[str] = []
    seen = set()
    for raw in variant_gids or []:
        gid = _to_variant_gid(str(raw))
        if gid and gid not in seen:
            seen.add(gid)
            gids.append(gid)
    if not gids:
        return None

    url = f"https://{shop}/admin/api/{SHOPIFY_API_VERSION}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": access_token,
        "Content-Type": "application/json",
    }

    query = """
    query ContextualPricing($ids: [ID!]!, $country: CountryCode!) {
      nodes(ids: $ids) {
        ... on ProductVariant {
          id
          contextualPricing(context: { country: $country }) {
            price {
              amount
              currencyCode
            }
          }
        }
      }
    }
    """

    out: dict[str, dict[str, Any]] = {}
    try:
        for i in range(0, len(gids), _BATCH):
            chunk = gids[i : i + _BATCH]
            resp = requests.post(
                url,
                headers=headers,
                json={
                    "query": query,
                    "variables": {"ids": chunk, "country": country},
                },
                timeout=30,
            )
            if resp.status_code == 401 or resp.status_code == 403:
                logger.warning(
                    "contextualPricing unauthorized (%s) — may need re-auth / Markets",
                    resp.status_code,
                )
                return None
            if resp.status_code >= 400:
                logger.warning(
                    "contextualPricing HTTP %s: %s",
                    resp.status_code,
                    (resp.text or "")[:200],
                )
                return None
            payload = resp.json()
            if payload.get("errors"):
                logger.warning("contextualPricing GraphQL errors: %s", payload["errors"][:2])
                # Still try to read partial data
            nodes = (payload.get("data") or {}).get("nodes") or []
            for node in nodes:
                if not node or not isinstance(node, dict):
                    continue
                vid = node.get("id") or ""
                price = ((node.get("contextualPricing") or {}).get("price") or {})
                amount_raw = price.get("amount")
                currency = str(price.get("currencyCode") or "").strip().upper()
                if amount_raw is None or not currency:
                    continue
                try:
                    amount = float(amount_raw)
                except (TypeError, ValueError):
                    continue
                entry = {"amount": amount, "currency": currency}
                num = _numeric_id(vid)
                if num:
                    out[num] = entry
                if vid:
                    out[str(vid)] = entry
    except requests.RequestException as e:
        logger.warning("contextualPricing request failed: %s", e)
        return None

    return out or None


_MARKETS_QUERY = """
query AdfeedMarkets {
  markets(first: 50) {
    nodes {
      enabled
      status
      regions(first: 250) {
        nodes {
          ... on MarketRegionCountry {
            code
          }
        }
      }
    }
  }
}
"""


def fetch_market_country_codes(
    shop_domain: str,
    access_token: str,
) -> Optional[set[str]]:
    """Return ISO country codes from enabled Shopify Markets regions.

    Returns ``None`` when the API cannot be read (missing scope / HTTP error).
    Returns an empty set when Markets exist but yield no country regions.
    """
    from .market_pricing import normalize_country_code
    from .shopify_admin_gql import graphql_payload

    if not shop_domain or not access_token:
        return None

    try:
        payload = graphql_payload(shop_domain, access_token, _MARKETS_QUERY)
    except Exception as e:
        logger.warning("markets query failed: %s", e)
        return None

    if payload.get("errors"):
        logger.warning("markets GraphQL errors: %s", (payload.get("errors") or [])[:2])
        return None

    nodes = ((payload.get("data") or {}).get("markets") or {}).get("nodes") or []
    if not nodes:
        return set()

    out: set[str] = set()
    for market in nodes:
        if market.get("enabled") is False:
            continue
        status = str(market.get("status") or "").strip().upper()
        if status and status not in ("ACTIVE",):
            continue
        for region in (market.get("regions") or {}).get("nodes") or []:
            code = (region.get("code") or "").strip()
            if code:
                out.add(normalize_country_code(code))
    return out
