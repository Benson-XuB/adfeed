"""Pre-generate product attribute gaps from Shopify options / store_db variants.

Merchants should see which products lack color or size *before* generating a feed,
so they can fix Shopify or decide what to select — not only after Multicolor/One Size autofix.
"""
from __future__ import annotations

from typing import Any

from .feed_quality import is_apparel_like


_PLACEHOLDER_COLORS = {"", "multicolor", "multicolour", "default title", "default", "nan"}
_PLACEHOLDER_SIZES = {"", "one size", "osfa", "default title", "default", "nan", "free size"}


def _blank_color(val: str) -> bool:
    import re

    low = str(val or "").strip().lower()
    if low in _PLACEHOLDER_COLORS:
        return True
    # "Style 1" / "Brown Style 1" are pattern noise, not a real GMC color.
    if re.search(r"(^|\s)style\s*\d+", low):
        return True
    return False


def _blank_size(val: str) -> bool:
    low = str(val or "").strip().lower()
    if low in _PLACEHOLDER_SIZES:
        return True
    # Dirty OSFA text left in Shopify options
    if "one size" in low or "osfa" in low or "均码" in low or "free size" in low:
        return True
    return False


def check_shopify_product_attrs(product: dict[str, Any]) -> dict[str, Any]:
    """Inspect one Shopify REST-shaped product for missing color/size.

    Returns:
        need_color / need_size booleans, plus empty variant counts.
    """
    from .store_sync import _option_maps, _variant_color_size

    title = str(product.get("title") or "")
    product_type = str(product.get("product_type") or "")
    apparel = is_apparel_like("", "", title, product_type)
    pos_to_name, _ = _option_maps(product)
    variants = list(product.get("variants") or [])

    empty_color = 0
    empty_size = 0
    for v in variants:
        color, size = _variant_color_size(v, pos_to_name)
        if _blank_color(color):
            empty_color += 1
        if _blank_size(size):
            empty_size += 1

    if not variants:
        return {
            "need_color": True,
            "need_size": True,
            "empty_color_variants": 0,
            "empty_size_variants": 0,
            "apparel": apparel,
        }

    # Merchant "check products" UX: any blank color/size on a variant is a gap.
    # (Includes Chinese apparel titles that do not match English apparel heuristics.)
    return {
        "need_color": empty_color > 0,
        "need_size": empty_size > 0,
        "empty_color_variants": empty_color,
        "empty_size_variants": empty_size,
        "apparel": apparel,
    }


def check_store_product_attrs(product, variants: list) -> dict[str, Any]:
    """Same gaps for a store_db Product + ProductVariant rows."""
    title = str(getattr(product, "title", "") or "")
    product_type = str(getattr(product, "product_type", "") or "")
    apparel = is_apparel_like(
        str(getattr(product, "gpc_path", "") or ""),
        str(getattr(product, "gpc_code", "") or ""),
        title,
        product_type,
    )
    if not variants:
        return {
            "need_color": True,
            "need_size": True,
            "empty_color_variants": 0,
            "empty_size_variants": 0,
            "apparel": apparel,
        }
    empty_color = sum(1 for v in variants if _blank_color(getattr(v, "color", "") or ""))
    empty_size = sum(1 for v in variants if _blank_size(getattr(v, "size", "") or ""))
    return {
        "need_color": empty_color > 0,
        "need_size": empty_size > 0,
        "empty_color_variants": empty_color,
        "empty_size_variants": empty_size,
        "apparel": apparel,
    }
