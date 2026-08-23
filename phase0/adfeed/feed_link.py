"""Build product landing URLs with currency pinning for feed crawlers."""
from __future__ import annotations

from typing import Iterable, Optional, Union
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def resolve_shopify_variant_id(
    primary: Optional[Union[str, int]] = None,
    *,
    candidates: Optional[Iterable[Optional[Union[str, int]]]] = None,
) -> Optional[str]:
    """Return a Shopify numeric variant id suitable for ``?variant=``.

    Rejects AdFeed internal hex SKUs and other non-numeric values so Feed
    links never impersonate a Shopify variant (wastes ad spend on wrong SKU).
    """
    ordered: list[Optional[Union[str, int]]] = []
    if primary is not None:
        ordered.append(primary)
    if candidates:
        ordered.extend(candidates)

    for raw in ordered:
        if raw is None:
            continue
        s = str(raw).strip()
        if s.isdigit():
            return s
    return None


def build_product_link(
    base_url: str,
    *,
    variant_id: Optional[str] = None,
    currency: Optional[str] = None,
) -> str:
    """Return a product URL with optional variant and currency query params.

    Always replaces an existing ``currency`` param so Feed currency matches
    what Shopify shows when Googlebot opens the link (IP-independent).
    """
    if not base_url or not str(base_url).strip():
        return ""

    parts = urlsplit(str(base_url).strip())
    query = dict(parse_qsl(parts.query, keep_blank_values=True))

    if variant_id is not None and str(variant_id).strip():
        query["variant"] = str(variant_id).strip()

    if currency is not None and str(currency).strip():
        query["currency"] = str(currency).strip().upper()

    new_query = urlencode(query)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, parts.fragment))
