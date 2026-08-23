"""Feed main-image picker — candidates, recommendation, DB patch (no AI edit)."""
from __future__ import annotations

import json
from typing import Any, Optional

from .image_processor import classify_image_risk


def parse_additional_images(raw: Optional[str]) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    text = str(raw).strip()
    if text.startswith("["):
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(u).strip() for u in parsed if str(u).strip()]
        except json.JSONDecodeError:
            pass
    return [u.strip() for u in text.split(",") if u.strip()]


def _candidate_entry(url: str, tags: list[str]) -> dict[str, Any]:
    risk = classify_image_risk(url)
    return {
        "url": url,
        "risky": bool(risk.get("risky")),
        "reason": str(risk.get("reason") or ""),
        "tags": tags,
    }


def build_candidates(
    *,
    product_image: str = "",
    additional: Optional[str] = None,
    variant_image: str = "",
    shopify_images: Optional[list[str]] = None,
) -> list[dict[str, Any]]:
    """Deduped candidate list with risk flags."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []

    def add(url: str, tags: list[str]) -> None:
        u = (url or "").strip()
        if not u or u in seen:
            return
        seen.add(u)
        out.append(_candidate_entry(u, tags))

    if variant_image:
        add(variant_image, ["variant_default"])
    if product_image and product_image != variant_image:
        add(product_image, ["product_featured"])
    for u in parse_additional_images(additional):
        add(u, ["product_gallery"])
    for u in shopify_images or []:
        add(u, ["shopify_live"])

    return out


def recommend_feed_image(candidates: list[dict[str, Any]]) -> str:
    """Pick best candidate URL for feed main image."""
    if not candidates:
        return ""

    def score(c: dict[str, Any]) -> tuple[int, int]:
        tags = c.get("tags") or []
        tag_bonus = 0
        if "variant_default" in tags:
            tag_bonus += 3
        elif "product_featured" in tags:
            tag_bonus += 2
        elif "shopify_live" in tags:
            tag_bonus += 1
        risky_penalty = 1 if c.get("risky") else 0
        shopify_bonus = 0 if "cdn.shopify.com" in str(c.get("url", "")).lower() else 1
        return (risky_penalty, shopify_bonus - tag_bonus)

    ordered = sorted(candidates, key=score)
    return str(ordered[0].get("url") or "")


def effective_feed_image(
    feed_image_url: Optional[str],
    variant_image: Optional[str],
    product_image: Optional[str],
) -> str:
    for u in (feed_image_url, variant_image, product_image):
        if u and str(u).strip():
            return str(u).strip()
    return ""


def fetch_shopify_product_images(shopify_domain: str, access_token: str, shopify_product_id: str) -> list[str]:
    if not shopify_domain or not access_token or not shopify_product_id:
        return []
    try:
        from .shopify_admin_gql import fetch_product_image_urls
        return fetch_product_image_urls(shopify_domain, access_token, shopify_product_id)
    except Exception:
        return []


def get_feed_image_context(store_id: str, sku: str) -> Optional[dict[str, Any]]:
    from . import store_db

    variant = store_db.get_variant_by_sku_for_store(store_id, sku)
    if not variant:
        return None
    product = store_db.get_product(variant.product_id)
    if not product or product.store_id != store_id:
        return None

    store = store_db.get_store(store_id)
    live: list[str] = []
    if store and store.access_token and store.shopify_domain and product.shopify_product_id:
        live = fetch_shopify_product_images(
            store.shopify_domain, store.access_token, product.shopify_product_id,
        )

    candidates = build_candidates(
        product_image=product.image_url or "",
        additional=product.additional_images,
        variant_image=variant.image_url or "",
        shopify_images=live,
    )
    effective = effective_feed_image(
        variant.feed_image_url, variant.image_url, product.image_url,
    )
    recommended = recommend_feed_image(candidates)

    return {
        "sku": sku,
        "product_id": product.id,
        "shopify_product_id": product.shopify_product_id or "",
        "product_title": product.title or "",
        "variant_color": variant.color or "",
        "current_feed_image": variant.feed_image_url or "",
        "effective_image": effective,
        "recommended_url": recommended,
        "candidates": candidates,
    }


def image_patch_and_regen(
    store_id: str,
    patches: list[dict],
    *,
    platforms: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    regenerate: bool = True,
) -> dict[str, Any]:
    from . import store_db
    from .pipeline import generate_feed_for_store

    apply = store_db.apply_feed_image_patches(store_id, patches)
    out: dict[str, Any] = {
        "updated": apply["updated"],
        "missing": apply["missing"],
        "invalid": apply.get("invalid", []),
        "feeds": [],
        "quality_report": None,
        "message": None,
    }
    if not apply["updated"]:
        out["message"] = "No matching SKUs to update"
        return out

    if not regenerate:
        out["message"] = f"Updated main image for {len(apply['updated'])} variant(s) (Feed not regenerated)"
        return out

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
        f"Updated main image for {len(apply['updated'])} variant(s) and regenerated Feed"
    )
    return out
