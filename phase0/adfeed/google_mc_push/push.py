"""Push durable feed rows into Merchant Center via productInputs.insert."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Optional

import httpx

from adfeed.feed_preview import parse_feed_file
from adfeed.google_mc_push.mapping import feed_row_to_product_input

_INSERT_URL = (
    "https://merchantapi.googleapis.com/products/v1/accounts/{account}/productInputs:insert"
)

# V1 sync hard cap (plan open question); UI should warn above this.
MAX_SYNC_ITEMS = 100


def _xml_item_to_row(item: dict[str, str]) -> dict[str, Any]:
    """Normalize parse_xml_items keys into mapping-friendly row."""
    return {
        "sku": item.get("id") or item.get("sku") or "",
        "title": item.get("title") or "",
        "description": item.get("description") or "",
        "link": item.get("link") or "",
        "image_link": item.get("image_link") or "",
        "price": item.get("price") or "",
        "availability": item.get("availability") or "in_stock",
        "condition": item.get("condition") or "new",
        "brand": item.get("brand") or "",
        "color": item.get("color") or "",
        "size": item.get("size") or "",
        "size_system": item.get("size_system") or "",
        "size_type": item.get("size_type") or "",
        "item_group_id": item.get("item_group_id") or "",
        "gtin": item.get("gtin") or "",
        "identifier_exists": item.get("identifier_exists") or "no",
        "pattern": item.get("pattern") or "",
        "material": item.get("material") or "",
        "gender": item.get("gender") or "",
        "age_group": item.get("age_group") or "",
    }


def load_pushable_rows(
    feed_path: Path,
    *,
    excluded_skus: set[str] | None = None,
    platform: str = "google",
) -> list[dict[str, Any]]:
    excluded = {str(s).strip() for s in (excluded_skus or set()) if str(s).strip()}
    items = parse_feed_file(feed_path, platform=platform)
    rows: list[dict[str, Any]] = []
    for item in items:
        row = _xml_item_to_row(item)
        sku = str(row.get("sku") or "").strip()
        if not sku or sku in excluded:
            continue
        rows.append(row)
    return rows


def insert_product_input(
    access_token: str,
    merchant_id: str,
    data_source_id: str,
    product_input: dict[str, Any],
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    account = str(merchant_id).strip()
    ds = str(data_source_id).strip()
    url = _INSERT_URL.format(account=account)
    params = {"dataSource": f"accounts/{account}/dataSources/{ds}"}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    owns = client is None
    http = client or httpx.Client(timeout=60.0)
    try:
        resp = http.post(url, headers=headers, params=params, json=product_input)
    finally:
        if owns:
            http.close()
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"insert failed: HTTP {resp.status_code} {resp.text[:400]}")
    return resp.json()


def push_rows(
    access_token: str,
    merchant_id: str,
    data_source_id: str,
    rows: list[dict[str, Any]],
    *,
    content_language: str = "en",
    feed_label: str = "US",
    insert_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if len(rows) > MAX_SYNC_ITEMS:
        raise ValueError(
            f"Too many items ({len(rows)}). V1 sync supports up to {MAX_SYNC_ITEMS}; "
            "narrow the feed or wait for background jobs."
        )
    do_insert = insert_fn or insert_product_input
    success = 0
    failures: list[dict[str, str]] = []
    with httpx.Client(timeout=60.0) as client:
        for row in rows:
            offer = str(row.get("sku") or "")
            try:
                body = feed_row_to_product_input(
                    row,
                    content_language=content_language,
                    feed_label=feed_label,
                )
                if insert_fn:
                    do_insert(
                        access_token,
                        merchant_id,
                        data_source_id,
                        body,
                    )
                else:
                    insert_product_input(
                        access_token,
                        merchant_id,
                        data_source_id,
                        body,
                        client=client,
                    )
                success += 1
            except Exception as exc:
                failures.append({"offer_id": offer, "error": str(exc)[:300]})
    return {
        "ok": True,
        "success_count": success,
        "failure_count": len(failures),
        "failures": failures[:50],
        "merchant_id": str(merchant_id),
        "data_source_id": str(data_source_id),
        "merchant_center_url": (
            f"https://merchants.google.com/mc/items"
            f"?a={merchant_id}&tab=online"
        ),
        "disclaimer": "Push submits products to Merchant Center; Google approval is not guaranteed.",
    }
