"""Analyze Google Shopping feed XML for marketing-site diagnostics."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import urlparse

import httpx

G_NS = {"g": "http://base.google.com/ns/1.0"}
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
DEFAULT_MAX_ITEMS = 500
TITLE_SOFT_LIMIT = 70
TITLE_NOISE_RE = re.compile(
    r"\b(new arrival|hot sale|free shipping|dropship|wholesale|factory|"
    r"supplier|best seller|high quality)\b",
    re.I,
)
DIRTY_BRAND_RE = re.compile(r"\b(eprolo|cjdropshipping|alibaba|1688|factory)\b", re.I)

# Map issue codes → overview categories (only rules we actually run).
CHECK_CATEGORY = {
    "missing_title": "titles",
    "noisy_or_long_title": "titles",
    "missing_brand": "brands",
    "dirty_brand": "brands",
    "missing_image": "images",
    "missing_color": "variants",
    "missing_size": "variants",
    "missing_identifier": "identifiers",
}

CHECK_LABELS = {
    "titles": "Title quality",
    "brands": "Brand",
    "images": "Main image",
    "variants": "Color / size (apparel)",
    "identifiers": "Product identifiers",
}


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text(item: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in item:
        if _local(child.tag).lower() in wanted:
            return (child.text or "").strip()
    for name in names:
        node = item.find(f"g:{name}", G_NS)
        if node is not None and (node.text or "").strip():
            return (node.text or "").strip()
    return ""


def _iter_items(root: ET.Element):
    if _local(root.tag).lower() == "item":
        yield root
        return
    for el in root.iter():
        if _local(el.tag).lower() == "item":
            yield el


def _bucket(
    buckets: dict[str, dict[str, Any]],
    code: str,
    *,
    label: str,
    advice: str,
    sample: dict[str, str] | None = None,
) -> None:
    b = buckets.setdefault(
        code,
        {"code": code, "label": label, "advice": advice, "count": 0, "samples": []},
    )
    b["count"] += 1
    if sample and len(b["samples"]) < 3:
        b["samples"].append(sample)


def _assessment(*, item_count: int, issue_types: int, affected: int) -> str:
    if item_count <= 0:
        return "No products found in this feed sample."
    if issue_types == 0:
        return "Your feed looks healthy in this check. No major catalog issues found."
    if affected >= max(1, int(item_count * 0.5)):
        return "Several product-data issues need attention before you lean on Google Shopping."
    return "Your feed needs some cleanup before running Google Shopping ads."


def analyze_feed_bytes(data: bytes, *, max_items: int = DEFAULT_MAX_ITEMS) -> dict[str, Any]:
    if not data:
        raise ValueError("Empty feed")
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("Feed file is too large")

    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError(f"Invalid XML: {exc}") from exc

    buckets: dict[str, dict[str, Any]] = {}
    item_count = 0
    truncated = False
    affected_ids: set[str] = set()
    scanned_categories: set[str] = {"titles", "brands", "images", "identifiers"}

    for item in _iter_items(root):
        if item_count >= max_items:
            truncated = True
            break
        item_count += 1
        offer_id = _child_text(item, "id")
        title = _child_text(item, "title")
        brand = _child_text(item, "brand")
        image = _child_text(item, "image_link")
        color = _child_text(item, "color")
        size = _child_text(item, "size")
        gtin = _child_text(item, "gtin")
        mpn = _child_text(item, "mpn")
        identifier_exists = _child_text(item, "identifier_exists").lower()
        product_type = _child_text(item, "product_type", "google_product_category")

        sample = {"id": offer_id or "(no id)", "title": (title or "")[:120]}
        hit = False

        if not brand:
            _bucket(
                buckets,
                "missing_brand",
                label="Missing brand",
                advice="Confirm your ad-facing brand in the catalog; do not leave supplier defaults blank.",
                sample=sample,
            )
            hit = True
        elif DIRTY_BRAND_RE.search(brand):
            _bucket(
                buckets,
                "dirty_brand",
                label="Supplier-looking brand",
                advice="Replace supplier/platform brand names with the brand shoppers should see in ads.",
                sample={**sample, "brand": brand},
            )
            hit = True

        if not title:
            _bucket(
                buckets,
                "missing_title",
                label="Missing title",
                advice="Every item needs a clear shopping title.",
                sample=sample,
            )
            hit = True
        else:
            noisy = len(title) > TITLE_SOFT_LIMIT or bool(TITLE_NOISE_RE.search(title))
            if noisy:
                _bucket(
                    buckets,
                    "noisy_or_long_title",
                    label="Title quality",
                    advice=(
                        "Supplier-style or overly long wording can make the product harder to match "
                        "to searches. Shorten the title and drop marketplace spam words. "
                        "This is a catalog quality issue, not an automatic Google rejection."
                    ),
                    sample=sample,
                )
                hit = True

        if not image:
            _bucket(
                buckets,
                "missing_image",
                label="Missing image",
                advice="Add a primary product image link for Shopping eligibility.",
                sample=sample,
            )
            hit = True

        apparelish = bool(
            re.search(r"apparel|clothing|dress|skirt|shirt|shoe|jacket", product_type, re.I)
            or re.search(r"\b(dress|skirt|shirt|tee|jacket|pants)\b", title, re.I)
        )
        if apparelish:
            scanned_categories.add("variants")
            if not color:
                _bucket(
                    buckets,
                    "missing_color",
                    label="Missing color",
                    advice="Set a real color attribute (not pattern/style mixed into color).",
                    sample=sample,
                )
                hit = True
            if not size:
                _bucket(
                    buckets,
                    "missing_size",
                    label="Missing size",
                    advice="Set size on apparel variants so Google can match shoppers.",
                    sample=sample,
                )
                hit = True

        has_id = bool(gtin or mpn)
        marked_no = identifier_exists in ("no", "false", "0")
        if not has_id and not marked_no:
            _bucket(
                buckets,
                "missing_identifier",
                label="Missing product identifiers",
                advice=(
                    "Use a compliant path without fake barcodes: set identifier_exists=no "
                    "when you have no GTIN, or provide a real GTIN/MPN you own. "
                    "Do not create fake GTINs."
                ),
                sample=sample,
            )
            hit = True

        if hit:
            affected_ids.add(offer_id or sample["id"])

    bucket_list = sorted(buckets.values(), key=lambda b: (-b["count"], b["code"]))
    issue_types = len(bucket_list)
    affected = len(affected_ids)
    ok_count = max(0, item_count - affected)

    failed_cats = {
        CHECK_CATEGORY[b["code"]]
        for b in bucket_list
        if b["code"] in CHECK_CATEGORY
    }
    checks_passed = [
        {"code": code, "label": CHECK_LABELS[code]}
        for code in ("titles", "brands", "images", "variants", "identifiers")
        if code in scanned_categories and code not in failed_cats
    ]
    issue_breakdown = []
    for b in bucket_list:
        cat = CHECK_CATEGORY.get(b["code"], b["code"])
        issue_breakdown.append(
            {
                "code": b["code"],
                "category": cat,
                "label": b["label"],
                "count": b["count"],
            }
        )

    return {
        "ok": True,
        "item_count": item_count,
        "truncated": truncated,
        "summary": {
            "assessment": _assessment(
                item_count=item_count, issue_types=issue_types, affected=affected
            ),
            "issue_types": issue_types,
            "affected_products": affected,
            "ok_products": ok_count,
            "issue_breakdown": issue_breakdown,
            "checks_passed": checks_passed,
        },
        "buckets": bucket_list,
        "adfeed_helps": [
            "Clean supplier-imported titles into concise Shopping titles",
            "Split color / size / pattern cleanly in the feed",
            "Confirm brand and use compliant no-GTIN handling (never fake barcodes)",
            "Publish a stable, always-synced Google Shopping feed URL",
        ],
        "adfeed_cannot": [
            "Create fake GTINs",
            "Bypass Google account-level suspensions",
            "Change your Merchant Center settings",
        ],
    }


def analyze_feed_url(
    url: str,
    *,
    max_items: int = DEFAULT_MAX_ITEMS,
    timeout: float = 30.0,
) -> dict[str, Any]:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("Feed URL must be http(s)")
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        with client.stream("GET", url.strip()) as resp:
            if resp.status_code != 200:
                raise ValueError(f"Could not download feed (HTTP {resp.status_code})")
            chunks: list[bytes] = []
            total = 0
            for chunk in resp.iter_bytes():
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise ValueError("Feed download exceeds size limit")
                chunks.append(chunk)
    return analyze_feed_bytes(b"".join(chunks), max_items=max_items)
