"""Bulk-confirm Multicolor / One Size fallbacks → DB + optional feed regen."""
from __future__ import annotations

from typing import Any, Optional


def bulk_patch_and_regen(
    store_id: str,
    patches: list[dict],
    *,
    platforms: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    regenerate: bool = True,
    shopify_product_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Persist color/size patches for store-owned SKUs, then regenerate feeds
    without re-running title/GPC optimize (no quota burn).
    """
    from . import store_db

    apply = store_db.apply_variant_attr_patches(
        store_id,
        patches,
        shopify_product_id=shopify_product_id,
    )
    out: dict[str, Any] = {
        "updated": apply["updated"],
        "missing": apply["missing"],
        "feeds": [],
        "quality_report": None,
        "message": None,
    }
    if not apply["updated"]:
        out["message"] = "No matching SKUs to update"
        return out

    if not regenerate:
        out["message"] = f"Updated {len(apply['updated'])} variant(s) (Feed not regenerated)"
        return out

    from .pipeline import generate_feed_for_store

    platforms = [p.lower() for p in (platforms or ["google"])] or ["google"]
    languages = [l.upper() for l in (languages or ["US"])] or ["US"]
    feeds = generate_feed_for_store(
        store_id=store_id,
        countries=languages,
        platforms=platforms,
    )
    out["feeds"] = feeds.get("feed_urls", [])
    out["quality_report"] = feeds.get("quality_report")
    out["blocked_countries"] = feeds.get("blocked_countries", [])
    out["message"] = feeds.get("message") or (
        f"Updated {len(apply['updated'])} variant(s) and regenerated Feed"
    )
    return out
