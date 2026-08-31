"""Per-variant GMC attribute cleaner (design-diff P0).

Cleans Shopify option noise, maps color/size to GMC English values,
fills size_system/size_type for apparel, Multicolor/One Size fallbacks.
"""
from __future__ import annotations

import re
from typing import Callable, Optional

from .feed_quality import QualityEvent, is_apparel_like

_NOISE_TOKENS = (
    "现货", "升级款", "新款", "爆款", "包邮", "热卖", "跨境",
    "in stock", "hot sale", "new arrival", "free shipping",
)

_OSFA_ALIASES = {
    "osfa", "0sfa", "one size", "one-size", "free size", "freesize",
    "均码", "自由码", "通用", "通用款",
}


def _strip_noise(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    for tok in _NOISE_TOKENS:
        text = re.sub(re.escape(tok), " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -/|,")
    return text


def _clean_size(raw: str) -> str:
    from .attribute_normalizer import normalize_size

    cleaned = _strip_noise(raw)
    if not cleaned:
        return ""
    low = cleaned.lower()
    if low in _OSFA_ALIASES or any(a in low for a in ("one size", "均码")):
        return "One Size"
    # Prefer trailing size token: "升级款 M" → after strip noise → "M"
    parts = cleaned.replace("/", " ").split()
    for part in reversed(parts):
        mapped = normalize_size(part)
        if mapped and re.match(
            r"^(XS|S|M|L|XL|XXL|XXXL|XXXXL|XXXXXL|2XL|3XL|4XL|5XL|One Size|\d{2,3})$",
            mapped,
            re.I,
        ):
            return mapped if mapped != "One Size" else "One Size"
        if part.upper() in ("XXL", "XXXL", "XXXXL", "XXXXXL", "2XL", "3XL", "4XL", "5XL"):
            return normalize_size(part) or part.upper()
    mapped = normalize_size(cleaned)
    return mapped or cleaned


def _clean_color(
    raw: str,
    title: str,
    description: str,
    extract_color_fn: Optional[Callable[[str, str], str]] = None,
) -> tuple[str, str]:
    """Return (color, source) source in variant|dict|llm|fallback."""
    from .attribute_normalizer import normalize_color, resolve_gmc_color, resolve_gmc_color_and_pattern

    cleaned = _strip_noise(raw)
    if cleaned:
        # Split print words out of color option (Pink Floral → Pink)
        hue, _pat = resolve_gmc_color_and_pattern(
            cleaned, description=description, title=title,
        )
        if hue and hue != "Multicolor":
            return hue, "variant"
        mapped = normalize_color(cleaned, "US")
        if mapped and mapped != "Multicolor":
            return mapped, "variant"
        resolved = resolve_gmc_color(cleaned, description=description, title=title)
        if resolved and resolved != "Multicolor":
            return resolved, "dict"

    # Empty / unresolved — try extract (LLM or inject in tests)
    extractor = extract_color_fn
    if extractor is None:
        try:
            from .color_extract import extract_color_from_text
            extractor = extract_color_from_text
        except Exception:
            extractor = None

    if extractor is not None:
        try:
            hit = (extractor(title or "", description or "") or "").strip()
            if hit and hit != "Multicolor":
                return hit, "llm"
            if hit == "Multicolor":
                return "Multicolor", "fallback"
        except Exception:
            pass

    return "Multicolor", "fallback"


def clean_variant_attributes(
    *,
    shopify_variant_id: str = "",
    color_raw: str = "",
    size_raw: str = "",
    title: str = "",
    description: str = "",
    gpc_path: str = "",
    gpc_code: str = "",
    product_type: str = "",
    extract_color_fn: Optional[Callable[[str, str], str]] = None,
    sku: str = "",
) -> dict:
    """Clean one variant into GMC color/size/system/type + QualityEvents."""
    apparel = is_apparel_like(gpc_path, gpc_code, title, product_type)
    events: list[QualityEvent] = []
    sku_key = sku or str(shopify_variant_id or "")

    color_before = (color_raw or "").strip()
    size_before = (size_raw or "").strip()

    g_color, color_source = _clean_color(
        color_raw, title, description, extract_color_fn=extract_color_fn,
    )
    from .attribute_normalizer import (
        extract_pattern_from_color_raw,
        opaque_style_axis_key,
        resolve_gmc_color_and_pattern,
    )
    # Prefer pattern from raw option even when color came from dict/LLM
    hue_from_raw, g_pattern = resolve_gmc_color_and_pattern(
        color_raw, description=description, title=title,
    )
    if not g_pattern:
        g_pattern = extract_pattern_from_color_raw(color_raw, hue=g_color)

    # Opaque Style/Design/Type axis → split item groups later; force real hue
    style_axis_key = opaque_style_axis_key(color_raw)
    if style_axis_key:
        if hue_from_raw and hue_from_raw != "Multicolor":
            g_color = hue_from_raw
            color_source = "dict"
        g_pattern = g_pattern or ""  # never invent Style N as pattern

    # Pure hue must never land in pattern (field contract)
    if g_color and g_pattern and g_pattern.lower() == g_color.lower():
        g_pattern = ""
    if g_color and g_color != "Multicolor" and (color_raw or "").strip().lower() == g_color.lower():
        g_pattern = ""

    # Non-apparel: never force Multicolor when the variant had no color
    if not apparel and g_color == "Multicolor" and not color_before:
        g_color = ""
        color_source = "variant"

    if apparel and not color_before and g_color == "Multicolor":
        events.append(QualityEvent(
            "AUTOFIX", "VA01", "g:color", sku_key,
            "变体缺颜色，已填 Multicolor",
            before=color_before, after="Multicolor",
        ))
    elif color_before and g_color and g_color != color_before:
        events.append(QualityEvent(
            "AUTOFIX", "VA01", "g:color", sku_key,
            f"颜色已清洗 → {g_color}",
            before=color_before, after=g_color,
        ))

    g_size = _clean_size(size_raw)
    if apparel and not g_size:
        g_size = "One Size"
        events.append(QualityEvent(
            "AUTOFIX", "VA02", "g:size", sku_key,
            "服装缺尺码，已填 One Size",
            before=size_before, after="One Size",
        ))
    elif size_before and g_size and g_size != size_before:
        events.append(QualityEvent(
            "AUTOFIX", "VA02", "g:size", sku_key,
            f"尺码已清洗 → {g_size}",
            before=size_before, after=g_size,
        ))

    g_size_system = ""
    g_size_type = ""
    if apparel:
        g_size_system = "US"
        g_size_type = "Regular"
        events.append(QualityEvent(
            "AUTOFIX", "VA03", "g:size_system", sku_key,
            "已补 size_system=US, size_type=Regular",
            before="", after="US/Regular",
        ))

    return {
        "shopify_variant_id": str(shopify_variant_id or "").strip(),
        "g_color": g_color,
        "g_pattern": g_pattern or "",
        "g_size": g_size,
        "g_size_system": g_size_system,
        "g_size_type": g_size_type,
        "style_axis_key": style_axis_key,
        "source": {"color": color_source, "size": "fallback" if g_size == "One Size" and not size_before else "variant"},
        "events": events,
    }
