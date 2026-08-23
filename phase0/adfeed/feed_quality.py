"""Generate-time feed quality: autofix + report (all categories).

FATAL rows still enter the feed; merchants decide whether to upload.
Apparel-like products with empty size → One Size (logged as autofix).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


APPAREL_PATH_HINTS = (
    "apparel", "clothing", "dress", "shirt", "top", "pant", "jean", "skirt",
    "sock", "shoe", "boot", "sandal", "sneaker", "jacket", "coat", "hoodie",
    "sweater", "underwear", "bra", "hat", "scarf", "glove", "belt", "bag",
    "handbag", "accessory", "swim", "activewear", "vest", "jumpsuit", "romper",
    "blouse", "legging", "short", "outerwear",
)

APPAREL_TITLE_HINTS = (
    "dress", "shirt", "top", "pant", "jean", "skirt", "sock", "shoe", "boot",
    "jacket", "coat", "hoodie", "sweater", "bra", "hat", "scarf", "glove",
    "belt", "bag", "tee", "t-shirt", "blouse", "legging", "short", "vest",
    "jumpsuit", "romper", "sandal", "sneaker", "underwear",
    # Common ZH apparel tokens (store titles often Chinese)
    "裙", "裤", "袜", "鞋", "靴", "夹克", "外套", "大衣", "帽", "手套",
    "内衣", "文胸", "衬衫", "T恤", "卫衣", "毛衣", "短裤", "连衣裙", "船袜",
)

# Size aliases that mean One Size Fits All — normalize to "One Size"
OSFA_ALIASES = frozenset({
    "osfa", "0sfa", "free size", "freesize", "均码", "one size fits all",
})


@dataclass
class QualityEvent:
    level: str  # AUTOFIX | WARN | FATAL
    rule_id: str
    field: str
    sku: str
    message: str
    suggestion: str = ""
    before: str = ""
    after: str = ""


@dataclass
class QualityReport:
    total_rows: int = 0
    autofixed: list[QualityEvent] = field(default_factory=list)
    warnings: list[QualityEvent] = field(default_factory=list)
    fatals: list[QualityEvent] = field(default_factory=list)
    checklist: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        def ser(ev: QualityEvent) -> dict:
            return {
                "level": ev.level,
                "rule_id": ev.rule_id,
                "field": ev.field,
                "sku": ev.sku,
                "message": ev.message,
                "suggestion": ev.suggestion,
                "before": ev.before,
                "after": ev.after,
            }

        return {
            "total_rows": self.total_rows,
            "light": traffic_light(self),
            "autofixed": [ser(e) for e in self.autofixed],
            "warnings": [ser(e) for e in self.warnings],
            "fatals": [ser(e) for e in self.fatals],
            "checklist": list(self.checklist),
            "summary": {
                "autofixed": len(self.autofixed),
                "warnings": len(self.warnings),
                "fatals": len(self.fatals),
            },
        }


def traffic_light(report: QualityReport) -> str:
    """Return green | yellow | red for the report."""
    if report.fatals:
        return "red"
    if report.autofixed or report.warnings:
        return "yellow"
    return "green"


def is_apparel_like(
    gpc_path: str = "",
    gpc_code: str = "",
    title: str = "",
    product_type: str = "",
) -> bool:
    """True for clothing, shoes, accessories — size often required by Google."""
    blob = f"{gpc_path} {product_type} {title}".lower()
    if any(h in blob for h in APPAREL_PATH_HINTS):
        return True
    if any(h in blob for h in APPAREL_TITLE_HINTS):
        return True
    # Common apparel GPC roots (Google taxonomy numeric prefixes vary; path is primary)
    code = str(gpc_code or "").strip()
    if code.startswith(("166", "1604", "187", "2271", "212", "178")):
        return True
    return False


def _sku(row: dict) -> str:
    return str(row.get("SKU") or row.get("sku") or "")


def _size_value(row: dict) -> str:
    for key in ("尺码", "size"):
        raw = row.get(key, "")
        if raw is None:
            continue
        s = str(raw).strip()
        if s and s.lower() != "nan":
            return s
    return ""


def _set_size(row: dict, value: str) -> None:
    row["尺码"] = value
    if "size" in row:
        row["size"] = value


def _brand_value(row: dict) -> str:
    for key in ("brand", "品牌"):
        raw = row.get(key, "")
        if raw is None:
            continue
        s = str(raw).strip()
        if s and s.lower() != "nan":
            return s
    return ""


def _set_brand(row: dict, value: str) -> None:
    if "品牌" in row and "brand" not in row:
        row["品牌"] = value
    else:
        row["brand"] = value
        if "品牌" in row:
            row["品牌"] = value


def _gtin_value(row: dict) -> str:
    for key in ("gtin", "GTIN", "barcode"):
        raw = row.get(key, "")
        if raw is None:
            continue
        s = str(raw).strip()
        if s and s.lower() not in ("nan", "none", "null"):
            return s
    return ""


def _color_value(row: dict) -> str:
    for key in ("颜色", "color"):
        raw = row.get(key, "")
        if raw is None:
            continue
        s = str(raw).strip()
        if s and s.lower() != "nan":
            return s
    return ""


def _set_color(row: dict, value: str) -> None:
    row["颜色"] = value
    if "color" in row:
        row["color"] = value


def _enrich_apparel_color(row: dict) -> list[QualityEvent]:
    """Apparel empty color: dict resolve → LLM extract → Multicolor autofill."""
    events: list[QualityEvent] = []
    sku = _sku(row)

    gpc_path = str(row.get("GPC路径") or row.get("gpc_path") or "")
    gpc_code = str(row.get("GPC代码") or row.get("gpc_code") or "")
    title = str(row.get("优化后标题") or row.get("标题") or row.get("title") or "")
    product_type = str(row.get("product_type") or "")
    description = str(row.get("描述") or row.get("description") or "")
    apparel = is_apparel_like(gpc_path, gpc_code, title, product_type)

    color_now = _color_value(row)
    # Never overwrite a good variant color (including existing Multicolor / Black)
    if not apparel or color_now:
        return events

    color: str = ""
    try:
        from .attribute_normalizer import resolve_gmc_color
        resolved = resolve_gmc_color(
            "",
            description=description,
            title=title,
        )
        if resolved and resolved != "Multicolor":
            color = resolved
    except Exception:
        pass

    if not color:
        try:
            from .color_extract import extract_color_from_text
            color = (extract_color_from_text(title, description) or "").strip()
        except Exception:
            color = ""

    if not color or color == "Multicolor":
        _set_color(row, "Multicolor")
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="C01",
            field="g:color",
            sku=sku,
            message="Apparel missing color — auto-filled Multicolor",
            suggestion="If the product has a real color, set Color on Shopify variants and regenerate",
            before="",
            after="Multicolor",
        ))
    else:
        _set_color(row, color)
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="C02",
            field="g:color",
            sku=sku,
            message=f"Extracted color from text → {color}",
            suggestion="",
            before="",
            after=color,
        ))
    return events


def enrich_and_autofix_row(row: dict, brand_fallback: str = "") -> list[QualityEvent]:
    """Color enrich (apparel) then attribute autofixes, then sensitive soften."""
    events = _enrich_apparel_color(row)
    events.extend(apply_row_autofixes(row, brand_fallback=brand_fallback))
    # S6a: after attribute autofixes; titles already optimized before process_feed_rows
    from .sensitive_compliance import apply_sensitive_compliance
    events.extend(apply_sensitive_compliance(row))
    return events


def apply_row_autofixes(row: dict, brand_fallback: str = "") -> list[QualityEvent]:
    """Mutate row with safe autofixes; return events."""
    events: list[QualityEvent] = []
    sku = _sku(row)

    gpc_path = str(row.get("GPC路径") or row.get("gpc_path") or "")
    gpc_code = str(row.get("GPC代码") or row.get("gpc_code") or "")
    title = str(row.get("优化后标题") or row.get("标题") or row.get("title") or "")
    product_type = str(row.get("product_type") or "")
    apparel = is_apparel_like(gpc_path, gpc_code, title, product_type)

    size_now = _size_value(row)
    if apparel and not size_now:
        _set_size(row, "One Size")
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="S01",
            field="g:size",
            sku=sku,
            message="Apparel missing size — auto-filled One Size",
            suggestion="If the product has real sizes, add Size on Shopify variants and regenerate",
            before="",
            after="One Size",
        ))
    elif size_now and size_now.strip().lower() in OSFA_ALIASES:
        before = size_now
        # Already canonical — do not re-nag every regen (socks / OSFA stay "needs size").
        if before.strip().lower() != "one size":
            _set_size(row, "One Size")
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="S05",
                field="g:size",
                sku=sku,
                message=f"Size alias normalized to One Size (was: {before})",
                suggestion="",
                before=before,
                after="One Size",
            ))
        else:
            _set_size(row, "One Size")

    # age_group default for apparel-like
    age = str(row.get("age_group") or "").strip()
    if apparel and not age:
        row["age_group"] = "adult"
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="S02",
            field="g:age_group",
            sku=sku,
            message="Defaulted age_group=adult",
            suggestion="For kids products, change to kids/toddler/infant in store settings",
        ))

    # S03: empty condition → new
    condition = str(row.get("condition") or "").strip()
    if not condition or condition.lower() == "nan":
        row["condition"] = "new"
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="S03",
            field="g:condition",
            sku=sku,
            message="Defaulted condition=new",
            suggestion="",
            before="",
            after="new",
        ))

    # S04: apparel gender empty/unisex → align with title (Women → female)
    gender = str(row.get("gender") or "").strip()
    if apparel:
        try:
            from .attribute_normalizer import normalize_gender
            seed = "" if gender.lower() in ("", "nan", "unisex") else gender
            inferred = normalize_gender(seed, title) or gender or "unisex"
        except Exception:
            inferred = gender or "unisex"
        if inferred and inferred != gender:
            row["gender"] = inferred
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="S04",
                field="g:gender",
                sku=sku,
                message=f"Aligned gender={inferred}",
                suggestion="Adjust to female / male / unisex based on category or title",
                before=gender,
                after=inferred,
            ))

    # ID01: no GTIN → identifier_exists=no + brand fallback
    if not _gtin_value(row):
        did_fix = False
        ident = str(row.get("identifier_exists") or "").strip().lower()
        if ident not in ("no", "false"):
            row["identifier_exists"] = "no"
            did_fix = True
        brand_now = _brand_value(row)
        if not brand_now and brand_fallback:
            _set_brand(row, brand_fallback)
            brand_now = brand_fallback
            did_fix = True
        if did_fix:
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="ID01",
                field="g:identifier_exists",
                sku=sku,
                message="No barcode — using identifier_exists=no"
                        + (f", brand={brand_now}" if brand_now else ""),
                suggestion="Add gtin if you have UPC/EAN; otherwise keep no-barcode and ensure brand is valid",
                before="",
                after="no",
            ))

    # ID02: myshopify.com brand → replace with fallback
    brand_now = _brand_value(row)
    if brand_now and "myshopify.com" in brand_now.lower():
        before = brand_now
        after = (brand_fallback or "").strip()
        if after:
            _set_brand(row, after)
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="ID02",
                field="g:brand",
                sku=sku,
                message=f"Brand contained myshopify.com — replaced with store brand {after}",
                suggestion="Set default_brand in store settings or use your custom-domain brand name",
                before=before,
                after=after,
            ))
        else:
            events.append(QualityEvent(
                level="WARN",
                rule_id="ID02",
                field="g:brand",
                sku=sku,
                message=f"Brand contains myshopify.com ({before}) — configure a valid store brand",
                suggestion="Set default_brand; do not use *.myshopify.com as brand",
                before=before,
                after="",
            ))

    # ── Material (apparel): translate CJK / infer from title / WARN if still empty ──
    events.extend(_autofix_material(row, apparel=apparel, sku=sku, title=title))

    # ── Description: format + EN labels; heavy CJK → English summary ──
    events.extend(_autofix_description(row, sku=sku, title=title))

    return events


_TITLE_MATERIAL_KEYWORDS = {
    "denim": "Denim", "jean": "Denim", "cotton": "Cotton",
    "silk": "Silk", "linen": "Linen", "wool": "Wool",
    "leather": "Leather", "polyester": "Polyester",
    "spandex": "Spandex", "nylon": "Nylon", "chiffon": "Chiffon",
}


def _material_value(row: dict) -> str:
    return str(row.get("材质") or row.get("material") or "").strip()


def _set_material(row: dict, value: str) -> None:
    row["材质"] = value
    row["material"] = value


def _autofix_material(row: dict, *, apparel: bool, sku: str, title: str) -> list[QualityEvent]:
    events: list[QualityEvent] = []
    raw = _material_value(row)

    if raw and any("\u4e00" <= c <= "\u9fff" for c in raw):
        try:
            from .feed_generator import _translate_material
            translated = (_translate_material(raw) or "").strip()
        except Exception:
            translated = ""
        if not translated:
            try:
                from .attribute_normalizer import normalize_material
                translated = (normalize_material(raw) or "").strip()
            except Exception:
                translated = ""
        if translated and not any("\u4e00" <= c <= "\u9fff" for c in translated):
            _set_material(row, translated)
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="M01",
                field="g:material",
                sku=sku,
                message=f"Material translated to English → {translated}",
                suggestion="Confirm it matches the actual product",
                before=raw,
                after=translated,
            ))
            raw = translated

    if apparel and not _material_value(row):
        import re
        inferred = ""
        desc = str(row.get("描述") or row.get("description") or "")
        m = re.search(
            r"(?:Fabric(?:\s+name)?|Material)\s*[:：]\s*([^\n<]+)",
            desc,
            re.I,
        )
        if m:
            line = m.group(1)
            line_l = line.lower()
            for kw, mat in _TITLE_MATERIAL_KEYWORDS.items():
                if kw in line_l:
                    inferred = mat
                    break
            if not inferred:
                try:
                    from .attribute_normalizer import normalize_material
                    inferred = (normalize_material(line.strip()) or "").strip()
                except Exception:
                    inferred = ""
        if not inferred:
            title_l = (title or "").lower()
            for kw, mat in _TITLE_MATERIAL_KEYWORDS.items():
                if kw in title_l:
                    inferred = mat
                    break
        if inferred:
            _set_material(row, inferred)
            events.append(QualityEvent(
                level="AUTOFIX",
                rule_id="M03",
                field="g:material",
                sku=sku,
                message=f"Inferred material from title/fabric line → {inferred}",
                suggestion="Add accurate fabric composition in Shopify",
                before="",
                after=inferred,
            ))
        else:
            events.append(QualityEvent(
                level="WARN",
                rule_id="M02",
                field="g:material",
                sku=sku,
                message="Apparel missing material — GMC may flag incomplete attributes",
                suggestion="Add fabric in Shopify product/description (e.g. Cotton / Polyester) and regenerate",
                before="",
                after="",
            ))
    return events


def _autofix_description(row: dict, *, sku: str, title: str) -> list[QualityEvent]:
    events: list[QualityEvent] = []
    from .desc_formatter import (
        prepare_feed_description,
        english_summary_from_fields,
        cjk_ratio,
    )

    desc_key = "描述" if "描述" in row else ("description" if "description" in row else "描述")
    raw = str(row.get(desc_key) or row.get("描述") or row.get("description") or "")
    if not raw.strip():
        return events

    formatted, meta = prepare_feed_description(raw)
    if meta.get("changed") and formatted:
        row[desc_key] = formatted
        row["描述"] = formatted
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="D02",
            field="g:description",
            sku=sku,
            message="Description formatted with English attribute labels where possible",
            suggestion="",
            before=raw[:120],
            after=formatted[:120],
        ))
        raw = formatted

    if meta.get("heavy_cjk") or cjk_ratio(str(row.get(desc_key) or "")) >= 0.35:
        summary = english_summary_from_fields(
            title=title or str(row.get("优化后标题") or row.get("标题") or ""),
            material=_material_value(row),
            color=str(row.get("颜色") or row.get("color") or ""),
            size=str(row.get("尺码") or row.get("size") or ""),
        )
        before = str(row.get(desc_key) or "")
        row[desc_key] = summary
        row["描述"] = summary
        events.append(QualityEvent(
            level="AUTOFIX",
            rule_id="D03",
            field="g:description",
            sku=sku,
            message="Description had heavy CJK text — replaced with English summary for GMC language consistency",
            suggestion="Add an English product description in Shopify and regenerate",
            before=before[:120],
            after=summary[:120],
        ))
        events.append(QualityEvent(
            level="WARN",
            rule_id="D01",
            field="g:description",
            sku=sku,
            message="Original description was mostly Chinese — English summary used as fallback",
            suggestion="English product details improve Shopping ad quality",
            before="",
            after="",
        ))
    return events


def diagnose_row_basics(row: dict) -> list[QualityEvent]:
    """Lightweight FATAL/WARN checks (rows still written to feed)."""
    events: list[QualityEvent] = []
    sku = _sku(row)

    title = str(row.get("优化后标题") or row.get("标题") or "").strip()
    if not title or title.lower() == "nan":
        events.append(QualityEvent(
            "FATAL", "T01", "g:title", sku, "Title is empty",
            "Add a valid product title and regenerate",
        ))

    img = str(row.get("图片链接") or row.get("image_url") or "").strip()
    if not img or img.lower() == "nan":
        events.append(QualityEvent(
            "FATAL", "I01", "g:image_link", sku, "Main image is empty",
            "Upload a main image in Shopify and regenerate",
        ))
    elif not img.startswith("http"):
        events.append(QualityEvent(
            "FATAL", "I02", "g:image_link", sku, "Main image is not an absolute URL",
            "Use an https image URL",
        ))
    else:
        from .image_processor import classify_image_risk
        risk = classify_image_risk(img)
        if risk.get("risky"):
            events.append(QualityEvent(
                "WARN", "I03", "g:image_link", sku,
                f"Main image may be from a wholesale platform ({risk.get('reason') or 'risky'})",
                suggestion="Pick a clean product photo from the gallery below",
                before=img, after=img,
            ))

    try:
        price = float(str(row.get("价格", 0)).replace("USD", "").replace("EUR", "").replace("CNY", "").strip() or 0)
    except ValueError:
        price = -1
    if price <= 0:
        events.append(QualityEvent(
            "FATAL", "P02", "g:price", sku, "Price is invalid or zero",
            "Set a valid price in Shopify and regenerate",
        ))

    link = str(row.get("链接") or "").strip()
    if not link or not link.startswith("http"):
        events.append(QualityEvent(
            "FATAL", "L01", "g:link", sku, "Product link is invalid",
            "Check store site URL and product handle",
        ))

    color = str(row.get("颜色") or row.get("color") or "").strip()
    gpc_path = str(row.get("GPC路径") or "")
    title = str(row.get("优化后标题") or row.get("标题") or "")
    if is_apparel_like(gpc_path, "", title) and (not color or color.lower() == "nan"):
        events.append(QualityEvent(
            "WARN", "V01", "g:color", sku, "Apparel should include a color",
            "Set Color on Shopify variants",
        ))

    return events


def process_feed_rows(rows: list[dict], brand_fallback: str = "") -> QualityReport:
    """Apply autofixes + diagnose; mutate rows in place."""
    report = QualityReport(total_rows=len(rows))
    report.checklist = [
        "Before uploading to Google, confirm shipping for the target country is set in Merchant Center",
        "Confirm your website is claimed and product pages are publicly accessible",
        "If FATAL issues remain, you upload at your own risk of disapproval",
    ]
    for row in rows:
        for ev in enrich_and_autofix_row(row, brand_fallback=brand_fallback):
            if ev.level == "FATAL":
                report.fatals.append(ev)
            elif ev.level == "WARN":
                report.warnings.append(ev)
            else:
                report.autofixed.append(ev)
        for ev in diagnose_row_basics(row):
            if ev.level == "FATAL":
                report.fatals.append(ev)
            else:
                report.warnings.append(ev)
    return report


def merge_reports(*reports: Optional[QualityReport]) -> QualityReport:
    out = QualityReport()
    for r in reports:
        if not r:
            continue
        out.total_rows += r.total_rows
        out.autofixed.extend(r.autofixed)
        out.warnings.extend(r.warnings)
        out.fatals.extend(r.fatals)
        for c in r.checklist:
            if c not in out.checklist:
                out.checklist.append(c)
    return out


def build_title_compare_samples(
    rows: list[dict],
    limit: int = 5,
) -> list[dict[str, str]]:
    """Pick before/after title pairs for quality UI (skip identical titles)."""
    samples: list[dict[str, str]] = []
    for row in rows or []:
        before = str(row.get("标题") or "").strip()
        after = str(row.get("优化后标题") or "").strip()
        if not before and not after:
            continue
        if before == after:
            continue
        samples.append({
            "sku": str(row.get("SKU") or ""),
            "before": before,
            "after": after,
        })
        if len(samples) >= limit:
            break
    return samples
