"""Row-level feed edits: title/color/size/image → owner layers + optional regen."""
from __future__ import annotations

from typing import Any, Optional


def apply_row_patches(store_id: str, patches: list[dict]) -> dict[str, Any]:
    """Apply per-SKU patches to variant owner fields (not XML literals)."""
    from . import store_db

    updated: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []

    for raw in patches or []:
        sku = str(raw.get("sku") or "").strip()
        if not sku:
            continue
        existing = store_db.get_variant_by_sku_for_store(store_id, sku)
        if not existing:
            missing.append(sku)
            continue

        color = raw.get("color")
        size = raw.get("size")
        title = raw.get("title")
        image_url = raw.get("image_url")

        touched = False
        if color is not None or size is not None:
            store_db.update_variant_attrs_for_store(
                store_id,
                sku,
                color=None if color is None else str(color).strip(),
                size=None if size is None else str(size).strip(),
            )
            touched = True

        if title is not None:
            t = str(title).strip()
            if t:
                store_db.update_variant_feed_title_for_store(store_id, sku, t)
                touched = True
            else:
                invalid.append(sku)

        if image_url is not None:
            url = str(image_url).strip()
            if url.startswith("http"):
                store_db.update_variant_feed_image_for_store(store_id, sku, url)
                touched = True
            elif url:
                invalid.append(sku)

        if touched:
            updated.append(sku)

    return {"updated": updated, "missing": missing, "invalid": invalid}


def row_patch_and_regen(
    store_id: str,
    patches: list[dict],
    *,
    platforms: Optional[list[str]] = None,
    languages: Optional[list[str]] = None,
    regenerate: bool = True,
) -> dict[str, Any]:
    apply = apply_row_patches(store_id, patches)
    out: dict[str, Any] = {
        "updated": apply["updated"],
        "missing": apply["missing"],
        "invalid": apply.get("invalid", []),
        "feeds": [],
        "quality_report": None,
        "message": None,
    }
    if not apply["updated"]:
        out["message"] = "No SKUs to update"
        return out

    if not regenerate:
        out["message"] = f"Updated {len(apply['updated'])} row(s) (feed not regenerated)"
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
        f"Updated {len(apply['updated'])} row(s) and regenerated feed"
    )
    return out


def delete_feed_rows(
    store_id: str,
    skus: list[str],
    *,
    platform: str = "google",
    country: str = "US",
) -> dict[str, Any]:
    """Remove SKUs from durable feed file; remember exclusion for future regen."""
    from pathlib import Path

    from . import store_db
    from .config import PUBLIC_BASE_URL
    from .feed_preview import remove_items_from_feed_file
    from .feed_snapshots import maybe_snapshot_current
    from .multi_platform_feeds import durable_feed_url

    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    sku_list = [str(s).strip() for s in (skus or []) if str(s).strip()]
    if not sku_list:
        return {
            "ok": False,
            "removed": [],
            "not_found": [],
            "message": "No SKUs to delete",
        }

    feed = store_db.get_store_feed(store_id, cu, plat)
    if not feed or not feed.file_path:
        return {
            "ok": False,
            "removed": [],
            "not_found": sku_list,
            "message": "Feed does not exist — generate first",
        }

    path = Path(feed.file_path)
    maybe_snapshot_current(store_id, plat, cu, path)
    result = remove_items_from_feed_file(path, sku_list, platform=plat)
    removed = result.get("removed") or []
    if removed:
        store_db.add_feed_excluded_skus(store_id, removed, cu, plat)
    item_count = int(result.get("item_count") or 0)
    feed_url = durable_feed_url(PUBLIC_BASE_URL, store_id, plat, cu)
    store_db.save_feed_file(
        store_id=store_id,
        country=cu,
        platform=plat,
        file_path=str(path),
        feed_url=feed_url,
        item_count=item_count,
    )
    not_found = result.get("not_found") or []
    if not removed:
        msg = "SKU not found in feed"
    else:
        msg = f"Removed {len(removed)} item(s) from feed (Shopify products unchanged)"
    return {
        "ok": bool(removed),
        "removed": removed,
        "not_found": not_found,
        "item_count": item_count,
        "url": feed_url,
        "message": msg,
    }
