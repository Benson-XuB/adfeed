"""Exact offer_id ↔ feed SKU matching. No fuzzy binding."""

from __future__ import annotations


def match_offer_to_sku(offer_id: str, sku_set: set[str]) -> str | None:
    oid = (offer_id or "").strip()
    if not oid or not sku_set:
        return None
    if oid in sku_set:
        return oid
    return None
