"""Public Shopify storefront check via products.json (no Admin API).

Limitations (intentional):
- Only public catalog pages Shopify exposes
- No GTIN / GMC disapproval / private inventory truth
- Rate-limited pages; max product cap
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from adfeed.public_tools.feed_checker import DIRTY_BRAND_RE, TITLE_NOISE_RE, TITLE_SOFT_LIMIT
from adfeed.public_tools.title_checker import analyze_title

MAX_PAGES = 5
PAGE_LIMIT = 50
MAX_PRODUCTS = 250
USER_AGENT = "AdFeedToolsShopifyCheck/1.0 (+https://deltfu.com/tools/shopify-checker)"

SHOP_RE = re.compile(r"^[a-z0-9][a-z0-9\-]*\.myshopify\.com$", re.I)


def normalize_shop_domain(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    if "://" not in s:
        s = "https://" + s
    try:
        host = urlparse(s).hostname or ""
    except Exception:
        return None
    host = host.lower().strip(".")
    if SHOP_RE.match(host):
        return host
    return None


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


def analyze_products_payload(
    payload: dict[str, Any],
    *,
    shop: str,
) -> dict[str, Any]:
    products = payload.get("products") or []
    buckets: dict[str, dict[str, Any]] = {}
    checked = 0

    for p in products:
        if checked >= MAX_PRODUCTS:
            break
        checked += 1
        title = (p.get("title") or "").strip()
        vendor = (p.get("vendor") or "").strip()
        pid = str(p.get("id") or "")
        sample = {"id": pid, "title": title[:120]}

        if not title:
            _bucket(
                buckets,
                "missing_title",
                label="Missing title",
                advice="Every product needs a shopper-readable title.",
                sample=sample,
            )
        else:
            tr = analyze_title(title)
            if TITLE_NOISE_RE.search(title) or len(title) > TITLE_SOFT_LIMIT:
                _bucket(
                    buckets,
                    "noisy_or_long_title",
                    label="Noisy or long title",
                    advice="Strip promo words; lead with audience + product + key attributes.",
                    sample=sample,
                )
            elif tr["verdict"] == "weak":
                _bucket(
                    buckets,
                    "weak_title",
                    label="Weak title",
                    advice="Add product type and known attributes shoppers search for.",
                    sample=sample,
                )

        if not vendor:
            _bucket(
                buckets,
                "missing_vendor",
                label="Missing vendor / brand signal",
                advice="Set a real store brand — not a blank vendor. Do not use supplier names as brand.",
                sample=sample,
            )
        elif DIRTY_BRAND_RE.search(vendor):
            _bucket(
                buckets,
                "dirty_vendor",
                label="Supplier-looking vendor",
                advice="Vendor looks like a supplier (e.g. eprolo). Use your ad brand instead.",
                sample={**sample, "vendor": vendor[:80]},
            )

        images = p.get("images") or []
        img = p.get("image") or {}
        has_img = bool(images) or bool((img or {}).get("src"))
        if not has_img:
            _bucket(
                buckets,
                "missing_image",
                label="Missing image",
                advice="Shopping needs at least one product image.",
                sample=sample,
            )

        options = p.get("options") or []
        option_names = {(o.get("name") or "").strip().lower() for o in options}
        variants = p.get("variants") or []
        has_color = "color" in option_names or "colour" in option_names
        has_size = "size" in option_names
        # Apparel-ish heuristic: multiple variants or color/size options
        if len(variants) > 1 or has_color or has_size:
            if not has_color:
                _bucket(
                    buckets,
                    "missing_color_option",
                    label="No color option",
                    advice="Apparel with variants usually needs a Color option for Shopping.",
                    sample=sample,
                )
            if not has_size:
                _bucket(
                    buckets,
                    "missing_size_option",
                    label="No size option",
                    advice="Apparel with variants usually needs a Size option for Shopping.",
                    sample=sample,
                )

    bucket_list = sorted(buckets.values(), key=lambda b: (-b["count"], b["code"]))
    issue_total = sum(b["count"] for b in bucket_list)
    return {
        "ok": True,
        "shop": shop,
        "products_checked": checked,
        "issue_total": issue_total,
        "buckets": bucket_list,
        "limits": {
            "max_products": MAX_PRODUCTS,
            "max_pages": MAX_PAGES,
            "page_limit": PAGE_LIMIT,
        },
        "disclaimer": (
            "Public products.json only — not Admin API. "
            "Cannot see GTIN, private apps, or Merchant Center disapprovals. "
            "Never invent barcodes or brands."
        ),
    }


def fetch_shop_products(shop: str) -> dict[str, Any]:
    domain = normalize_shop_domain(shop)
    if not domain:
        raise ValueError("Enter a *.myshopify.com store URL (e.g. your-store.myshopify.com)")

    all_products: list[dict[str, Any]] = []
    with httpx.Client(timeout=25.0, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        for page in range(1, MAX_PAGES + 1):
            url = f"https://{domain}/products.json?limit={PAGE_LIMIT}&page={page}"
            resp = client.get(url)
            if resp.status_code == 404:
                raise ValueError("Store not found or products.json is not public")
            if resp.status_code != 200:
                raise RuntimeError(f"Shopify HTTP {resp.status_code}: {resp.text[:200]}")
            data = resp.json()
            batch = data.get("products") or []
            if not batch:
                break
            all_products.extend(batch)
            if len(batch) < PAGE_LIMIT or len(all_products) >= MAX_PRODUCTS:
                break

    return analyze_products_payload({"products": all_products[:MAX_PRODUCTS]}, shop=domain)
