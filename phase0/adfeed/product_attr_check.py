"""Pre-generate product attribute gaps from Shopify options / store_db variants.

Policy (field contract §3 — 缺数据不挡生成):
- Color/size gaps are **soft suggestions** when Shopify has a named option we can edit.
- No Color/Size option on the product → **skip** (do not open dead-end Fix; do not block generate).
- Engine may fill apparel Multicolor / One Size at generate time; never invent brand/GTIN/COGS.
"""
from __future__ import annotations

from typing import Any

from .feed_quality import is_apparel_like


_PLACEHOLDER_COLORS = {"", "multicolor", "multicolour", "default title", "default", "nan"}
_PLACEHOLDER_SIZES = {"", "one size", "osfa", "default title", "default", "nan", "free size"}

_COLOR_KEYS = ("color", "colour", "farbe", "颜色", "couleur")
_SIZE_KEYS = ("size", "größe", "taille", "尺码", "sizing")


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


def _has_named_option(pos_to_name: dict, keys: tuple[str, ...]) -> bool:
    return any(
        any(k in str(n or "").lower() for k in keys)
        for n in pos_to_name.values()
    )


def check_shopify_product_attrs(product: dict[str, Any]) -> dict[str, Any]:
    """Inspect one Shopify REST-shaped product for missing color/size.

    need_color / need_size mean: optional Fix is available (named option + blank/placeholder).
    They must NOT be treated as hard generate blockers by the workbench.
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

    has_color_option = _has_named_option(pos_to_name, _COLOR_KEYS)
    has_size_option = _has_named_option(pos_to_name, _SIZE_KEYS)

    if not variants:
        return {
            "need_color": False,
            "need_size": False,
            "empty_color_variants": 0,
            "empty_size_variants": 0,
            "apparel": apparel,
            "has_color_option": has_color_option,
            "has_size_option": has_size_option,
        }

    return {
        # Soft Fix only when Shopify has an editable named option.
        "need_color": empty_color > 0 and has_color_option,
        "need_size": empty_size > 0 and has_size_option,
        "empty_color_variants": empty_color,
        "empty_size_variants": empty_size,
        "apparel": apparel,
        "has_color_option": has_color_option,
        "has_size_option": has_size_option,
    }


def check_store_product_attrs(product, variants: list) -> dict[str, Any]:
    """Same gaps for store_db rows.

    store_db has no option names — cannot know if Fix is possible → never force Fix.
    """
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
            "need_color": False,
            "need_size": False,
            "empty_color_variants": 0,
            "empty_size_variants": 0,
            "apparel": apparel,
        }
    empty_color = sum(1 for v in variants if _blank_color(getattr(v, "color", "") or ""))
    empty_size = sum(1 for v in variants if _blank_size(getattr(v, "size", "") or ""))
    return {
        "need_color": False,
        "need_size": False,
        "empty_color_variants": empty_color,
        "empty_size_variants": empty_size,
        "apparel": apparel,
    }
