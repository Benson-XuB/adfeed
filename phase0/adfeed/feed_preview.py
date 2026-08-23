"""Parse durable feed files into paginated preview rows for App UI."""
from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any, Optional
from xml.sax.saxutils import unescape


_G_TAG = re.compile(r"<g:(\w+)>(.*?)</g:\1>", re.DOTALL)
_PLAIN_TAG = re.compile(r"<(\w+)>(.*?)</\1>", re.DOTALL)
_ITEM_BLOCK = re.compile(r"<item>(.*?)</item>", re.DOTALL)


def _decode(val: str) -> str:
    return unescape(val.strip()).replace("&#39;", "'")


def parse_xml_items(content: str) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    for block in _ITEM_BLOCK.findall(content or ""):
        row: dict[str, str] = {}
        for m in _G_TAG.finditer(block):
            key, val = m.group(1), _decode(m.group(2))
            if key in row and key.startswith("additional_image"):
                row[key] = f"{row[key]},{val}"
            else:
                row[key] = val
        if not row:
            for m in _PLAIN_TAG.finditer(block):
                key = m.group(1)
                if key in ("item",):
                    continue
                row[key] = _decode(m.group(2))
        if row:
            items.append(row)
    return items


def parse_csv_items(content: str) -> list[dict[str, str]]:
    reader = csv.DictReader(io.StringIO(content or ""))
    return [{k: (v or "") for k, v in row.items()} for row in reader]


def parse_feed_file(path: Path, platform: str = "google") -> list[dict[str, str]]:
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    plat = (platform or "google").lower()
    if plat == "tiktok" or path.suffix.lower() == ".csv":
        return parse_csv_items(text)
    return parse_xml_items(text)


def item_to_preview_row(item: dict[str, str], *, issue: str = "") -> dict[str, Any]:
    sku = item.get("id") or item.get("sku_id") or item.get("sku") or ""
    return {
        "sku": sku,
        "title": item.get("title") or "",
        "color": item.get("color") or "",
        "size": item.get("size") or "",
        "price": item.get("price") or "",
        "image_url": item.get("image_link") or item.get("image_url") or "",
        "link": item.get("link") or item.get("product_url") or "",
        "item_group_id": item.get("item_group_id") or "",
        "issue": issue,
    }


def resolve_product_feed_filter(store_id: str, product_id: str) -> dict[str, Any]:
    """Map Shopify/internal product id → SKUs + item_group prefixes for feed filter."""
    from . import store_db

    pid = str(product_id or "").strip()
    skus: set[str] = set()
    prefixes: set[str] = set()
    if not pid:
        return {"skus": skus, "group_prefixes": prefixes, "internal_id": ""}

    prefixes.add(pid)
    match = None
    for p in store_db.get_store_products(store_id):
        sp = str(p.shopify_product_id or "").strip()
        if sp == pid or str(p.id) == pid:
            match = p
            break
    if match:
        if match.shopify_product_id:
            prefixes.add(str(match.shopify_product_id))
        prefixes.add(str(match.id))
        for v in store_db.get_product_variants(match.id):
            if v.sku:
                skus.add(str(v.sku))
    return {
        "skus": skus,
        "group_prefixes": prefixes,
        "internal_id": match.id if match else "",
    }


def _item_matches_product(item: dict[str, str], skus: set[str], prefixes: set[str]) -> bool:
    sku = str(item.get("id") or item.get("sku") or "").strip()
    if sku and sku in skus:
        return True
    gid = str(item.get("item_group_id") or "").strip()
    if not gid:
        return False
    for p in prefixes:
        if not p:
            continue
        if gid == p or gid.startswith(f"{p}-"):
            return True
    return False


def internal_ids_in_durable_feeds(
    store_id: str,
    *,
    platforms: list[str],
    countries: list[str],
) -> set[str]:
    """Internal product ids that already appear in durable feed files.

    Used by merge-generate: keep existing feed membership, add newly optimized ids.
    """
    from . import store_db
    from .config import FEEDS_DIR
    from .multi_platform_feeds import durable_feed_path

    products = store_db.get_store_products(store_id)
    filters: list[dict[str, Any]] = []
    for p in products:
        filt = resolve_product_feed_filter(store_id, p.shopify_product_id or p.id)
        if filt.get("internal_id"):
            filters.append(filt)

    found: set[str] = set()
    plats = [str(p or "google").lower() for p in (platforms or ["google"])]
    cus = [str(c or "US").upper() for c in (countries or ["US"])]
    for plat in plats:
        for cu in cus:
            path = durable_feed_path(FEEDS_DIR, store_id, plat, cu)
            items = parse_feed_file(path, plat)
            if not items:
                continue
            for filt in filters:
                iid = str(filt.get("internal_id") or "")
                if not iid or iid in found:
                    continue
                if any(
                    _item_matches_product(it, filt["skus"], filt["group_prefixes"])
                    for it in items
                ):
                    found.add(iid)
    return found


def _issue_map_from_quality(quality_report: Optional[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    if not isinstance(quality_report, dict):
        return out
    for severity, key in (("fatal", "fatals"), ("warn", "warnings")):
        for ev in quality_report.get(key) or []:
            if not isinstance(ev, dict):
                continue
            sku = str(ev.get("sku") or "").strip()
            if not sku:
                continue
            msg = str(ev.get("message") or ev.get("rule_id") or severity)
            prev = out.get(sku)
            out[sku] = f"{prev}; {msg}" if prev else f"{severity}: {msg}"
    return out


def preview_feed_items(
    *,
    file_path: str,
    platform: str = "google",
    limit: int = 20,
    offset: int = 0,
    q: str = "",
    quality_report: Optional[dict] = None,
    product_id: str = "",
    store_id: str = "",
) -> dict[str, Any]:
    limit = max(1, min(int(limit or 20), 200))
    offset = max(0, int(offset or 0))
    needle = (q or "").strip().lower()

    raw = parse_feed_file(Path(file_path), platform)
    if product_id and store_id:
        filt = resolve_product_feed_filter(store_id, product_id)
        raw = [
            it
            for it in raw
            if _item_matches_product(it, filt["skus"], filt["group_prefixes"])
        ]

    issues = _issue_map_from_quality(quality_report)
    rows = [
        item_to_preview_row(
            it,
            issue=issues.get(it.get("id") or it.get("sku") or "", ""),
        )
        for it in raw
    ]

    if needle:
        rows = [
            r
            for r in rows
            if needle in (r.get("sku") or "").lower()
            or needle in (r.get("title") or "").lower()
            or needle in (r.get("color") or "").lower()
        ]

    total = len(rows)
    page = rows[offset : offset + limit]
    return {
        "items": page,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
        "product_id": product_id or None,
    }


def _is_multicolor_fallback(ev: dict) -> bool:
    after = str(ev.get("after") or "").strip().lower().replace(" ", "")
    return after in {"multicolor", "multicolour"}


def _is_onesize_fallback(ev: dict) -> bool:
    rule = str(ev.get("rule_id") or "").upper()
    after = str(ev.get("after") or "").strip().lower()
    before = str(ev.get("before") or "").strip().lower()
    if rule == "S05":
        return False
    # S01 empty→One Size; VA02 dirty OSFA text cleaned → One Size (still needs merchant review)
    if rule in {"S01", "VA02"}:
        return after in {"one size", "osfa"} or "one size" in after
    if after in {"one size", "osfa"}:
        return (not before) or ("one size" in before) or ("osfa" in before) or ("均码" in before)
    return False


def _feed_item_color_gap(item: dict[str, str]) -> bool:
    import re

    raw = str(item.get("color") or "").strip().lower()
    c = raw.replace(" ", "")
    if c in {"multicolor", "multicolour", ""}:
        return True
    if re.search(r"(^|\s)style\s*\d+", raw):
        return True
    return False


def _feed_item_size_gap(item: dict[str, str]) -> bool:
    s = str(item.get("size") or "").strip().lower()
    if not s or s in {"one size", "osfa"}:
        return True
    if "one size" in s or "osfa" in s:
        return True
    return False


def _sku_sets_from_quality(quality_report: Optional[dict]) -> dict[str, set[str]]:
    """SKU sets that need merchant attention after generate autofixes."""
    qr = quality_report if isinstance(quality_report, dict) else {}
    color: set[str] = set()
    size: set[str] = set()
    image: set[str] = set()
    fatal: set[str] = set()
    warn: set[str] = set()
    for ev in qr.get("autofixed") or []:
        if not isinstance(ev, dict):
            continue
        sku = str(ev.get("sku") or "").strip()
        if not sku:
            continue
        if _is_multicolor_fallback(ev):
            color.add(sku)
        if _is_onesize_fallback(ev):
            size.add(sku)
    for ev in qr.get("warnings") or []:
        if not isinstance(ev, dict):
            continue
        sku = str(ev.get("sku") or "").strip()
        if not sku:
            continue
        warn.add(sku)
        if str(ev.get("rule_id") or "").upper() == "I03":
            image.add(sku)
    for ev in qr.get("fatals") or []:
        if not isinstance(ev, dict):
            continue
        sku = str(ev.get("sku") or "").strip()
        if sku:
            fatal.add(sku)
    return {
        "color": color,
        "size": size,
        "image": image,
        "fatal": fatal,
        "warn": warn,
    }


def build_workbench_product_rows(
    *,
    store_id: str,
    file_path: str,
    platform: str,
    products: list[dict[str, Any]],
    quality_report: Optional[dict] = None,
) -> list[dict[str, Any]]:
    """Attach feed item counts + Ready/Missing status onto product rows."""
    raw = parse_feed_file(Path(file_path), platform) if file_path else []
    issues = _issue_map_from_quality(quality_report)
    sku_sets = _sku_sets_from_quality(quality_report)

    out: list[dict[str, Any]] = []
    for p in products:
        pid = str(p.get("id") or "")
        filt = resolve_product_feed_filter(store_id, pid)
        matched = [
            it
            for it in raw
            if _item_matches_product(it, filt["skus"], filt["group_prefixes"])
        ]
        skus = [str(it.get("id") or "") for it in matched]
        if p.get("gaps_from_store_db"):
            need_color = bool(p.get("need_color"))
            need_size = bool(p.get("need_size"))
        else:
            need_color = bool(p.get("need_color")) or any(
                s in sku_sets["color"] for s in skus
            )
            need_size = bool(p.get("need_size")) or any(
                s in sku_sets["size"] for s in skus
            )
            # Placeholders already in durable feed (skip when store_db gaps are authoritative).
            if any(_feed_item_color_gap(it) for it in matched):
                need_color = True
            if any(_feed_item_size_gap(it) for it in matched):
                need_size = True
        need_image = any(s in sku_sets["image"] for s in skus)
        has_fatal = any(s in sku_sets["fatal"] for s in skus) or any(
            (issues.get(s) or "").startswith("fatal") for s in skus
        )
        has_warn = any(s in sku_sets["warn"] for s in skus)
        needs_attrs = need_color or need_size or need_image
        if not matched:
            # Not in feed yet — keep pending, but still flag Shopify option gaps.
            status = "pending"
        elif has_fatal:
            status = "missing"
        elif has_warn or needs_attrs:
            status = "warn"
        else:
            status = "ready"
        out.append({
            **p,
            "feed_item_count": len(matched),
            "feed_status": status,
            "need_color": need_color,
            "need_size": need_size,
            "need_image": need_image,
            "needs_attention": bool(needs_attrs or has_fatal or has_warn),
        })
    return out


def _item_block_sku(block_inner: str) -> str:
    for pat in (
        re.compile(r"<g:id>(.*?)</g:id>", re.DOTALL),
        re.compile(r"<id>(.*?)</id>", re.DOTALL),
        re.compile(r"<g:sku_id>(.*?)</g:sku_id>", re.DOTALL),
        re.compile(r"<sku_id>(.*?)</sku_id>", re.DOTALL),
    ):
        m = pat.search(block_inner or "")
        if m:
            return _decode(m.group(1))
    return ""


def remove_items_from_xml(content: str, skus: set[str]) -> tuple[str, list[str]]:
    """Drop <item> blocks whose g:id is in skus. Preserves outer XML shell."""
    targets = {str(s).strip() for s in skus if str(s).strip()}
    removed: list[str] = []

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1) or ""
        sku = _item_block_sku(inner)
        if sku and sku in targets:
            removed.append(sku)
            return ""
        return match.group(0)

    new_content = _ITEM_BLOCK.sub(repl, content or "")
    return new_content, removed


def remove_items_from_csv(content: str, skus: set[str]) -> tuple[str, list[str]]:
    targets = {str(s).strip() for s in skus if str(s).strip()}
    if not (content or "").strip():
        return content or "", []
    sample = content[:4096]
    delimiter = "\t" if "\t" in sample.splitlines()[0] else ","
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    if not reader.fieldnames:
        return content, []
    kept: list[dict[str, str]] = []
    removed: list[str] = []
    for row in reader:
        rid = str(
            row.get("id") or row.get("sku_id") or row.get("sku") or ""
        ).strip()
        if rid and rid in targets:
            removed.append(rid)
            continue
        kept.append(row)
    out = io.StringIO()
    w = csv.DictWriter(
        out,
        fieldnames=list(reader.fieldnames),
        delimiter=delimiter,
        extrasaction="ignore",
    )
    w.writeheader()
    for row in kept:
        w.writerow(row)
    return out.getvalue(), removed


def count_feed_items(content: str, platform: str = "google", path: Optional[Path] = None) -> int:
    plat = (platform or "google").lower()
    suffix = (path.suffix.lower() if path else "") or ""
    if plat == "tiktok" or suffix == ".csv":
        lines = [ln for ln in (content or "").splitlines() if ln.strip()]
        return max(0, len(lines) - 1) if lines else 0
    return len(parse_xml_items(content))


def remove_items_from_feed_file(
    path: Path,
    skus: list[str],
    *,
    platform: str = "google",
) -> dict[str, Any]:
    """Remove SKU rows from durable feed file; refresh sidecar CSV when Google XML."""
    sku_list = [str(s).strip() for s in (skus or []) if str(s).strip()]
    if not path.exists() or not sku_list:
        return {"removed": [], "item_count": 0, "not_found": sku_list}
    plat = (platform or "google").lower()
    content = path.read_text(encoding="utf-8", errors="replace")
    targets = set(sku_list)
    if plat == "tiktok" or path.suffix.lower() == ".csv":
        new_content, removed = remove_items_from_csv(content, targets)
    else:
        new_content, removed = remove_items_from_xml(content, targets)
    path.write_text(new_content, encoding="utf-8")
    item_count = count_feed_items(new_content, plat, path)
    if plat == "google" and path.suffix.lower() == ".xml":
        write_google_tsv_from_xml(path, path.with_suffix(".csv"))
    not_found = [s for s in sku_list if s not in removed]
    return {"removed": removed, "item_count": item_count, "not_found": not_found}


def write_google_tsv_from_xml(xml_path: Path, csv_path: Path) -> int:
    """Write tab-delimited Google CSV beside XML for download."""
    items = parse_xml_items(xml_path.read_text(encoding="utf-8", errors="replace"))
    if not items:
        csv_path.write_text("", encoding="utf-8")
        return 0
    fields: list[str] = []
    seen: set[str] = set()
    preferred = [
        "id", "title", "description", "link", "image_link", "additional_image_link",
        "availability", "price", "brand", "condition", "item_group_id", "color", "size",
        "gender", "age_group", "identifier_exists", "gtin", "mpn",
    ]
    for f in preferred:
        if any(f in it for it in items) and f not in seen:
            fields.append(f)
            seen.add(f)
    for it in items:
        for k in it:
            if k not in seen:
                fields.append(k)
                seen.add(k)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        for it in items:
            w.writerow(it)
    return len(items)
