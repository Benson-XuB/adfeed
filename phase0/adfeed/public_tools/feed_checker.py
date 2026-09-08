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


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def _child_text(item: ET.Element, *names: str) -> str:
    wanted = {n.lower() for n in names}
    for child in item:
        if _local(child.tag).lower() in wanted:
            return (child.text or "").strip()
    # namespaced g: lookups
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

        if not brand:
            _bucket(
                buckets,
                "missing_brand",
                label="Missing brand",
                advice="Confirm your ad-facing brand in the catalog; do not leave supplier defaults blank.",
                sample=sample,
            )
        elif DIRTY_BRAND_RE.search(brand):
            _bucket(
                buckets,
                "dirty_brand",
                label="Supplier-looking brand",
                advice="Replace supplier/platform brand names with the brand shoppers should see in ads.",
                sample={**sample, "brand": brand},
            )

        if not title:
            _bucket(
                buckets,
                "missing_title",
                label="Missing title",
                advice="Every item needs a clear shopping title.",
                sample=sample,
            )
        else:
            noisy = len(title) > TITLE_SOFT_LIMIT or bool(TITLE_NOISE_RE.search(title))
            if noisy:
                _bucket(
                    buckets,
                    "noisy_or_long_title",
                    label="Noisy or long title",
                    advice="Shorten titles; drop supplier spam words. AdFeed can regenerate cleaner Shopping titles.",
                    sample=sample,
                )

        if not image:
            _bucket(
                buckets,
                "missing_image",
                label="Missing image",
                advice="Add a primary product image link for Shopping eligibility.",
                sample=sample,
            )

        apparelish = bool(
            re.search(r"apparel|clothing|dress|skirt|shirt|shoe|jacket", product_type, re.I)
            or re.search(r"\b(dress|skirt|shirt|tee|jacket|pants)\b", title, re.I)
        )
        if apparelish:
            if not color:
                _bucket(
                    buckets,
                    "missing_color",
                    label="Missing color",
                    advice="Set a real color attribute (not pattern/style mixed into color).",
                    sample=sample,
                )
            if not size:
                _bucket(
                    buckets,
                    "missing_size",
                    label="Missing size",
                    advice="Set size on apparel variants so Google can match shoppers.",
                    sample=sample,
                )

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

    return {
        "ok": True,
        "item_count": item_count,
        "truncated": truncated,
        "buckets": sorted(buckets.values(), key=lambda b: (-b["count"], b["code"])),
        "adfeed_helps": [
            "Clean noisy 1688/supplier titles into concise Shopping titles",
            "Split color / size / pattern cleanly in the feed",
            "Confirm brand and use compliant no-GTIN handling (never fake barcodes)",
            "Publish a stable, always-synced Google feed URL",
        ],
        "adfeed_cannot": [
            "Create fake GTINs or override Google account-level policy suspensions",
            "Change your Merchant Center settings without you connecting Google later",
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
