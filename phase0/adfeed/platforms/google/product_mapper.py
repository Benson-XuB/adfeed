"""Map canonical Chinese-key feed rows → Merchant API ProductInput JSON.

Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md

Thin export mapper only — pass through quality-engine row values.
Never invent color/brand/gtin; empty color → omit (no Multicolor).
"""
from __future__ import annotations

import re
from typing import Any, Mapping, MutableMapping, Optional

_AVAIL_ENUM = {
    "in_stock": "IN_STOCK",
    "out_of_stock": "OUT_OF_STOCK",
    "preorder": "PREORDER",
    "backorder": "BACKORDER",
    "limited_availability": "LIMITED_AVAILABILITY",
}

_CONDITION_ENUM = {
    "new": "NEW",
    "used": "USED",
    "refurbished": "REFURBISHED",
}


def _str(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        if key not in row:
            continue
        val = row.get(key)
        if val is None:
            continue
        text = str(val).strip()
        if text.lower() in ("", "nan", "none"):
            continue
        return text
    return ""


def _price_amount(row: Mapping[str, Any]) -> Optional[float]:
    raw = row.get("价格", row.get("price"))
    if raw is None or raw == "":
        return None
    try:
        return float(str(raw).replace(",", "").strip().split()[0])
    except (TypeError, ValueError, IndexError):
        return None


def _currency(row: Mapping[str, Any], feed_label: str) -> str:
    for key in ("_feed_currency", "currency", "币种"):
        text = _str(row, key)
        if text:
            return text.upper()
    # Feed label is often a country code; default USD for US, else uppercase label.
    label = (feed_label or "US").strip().upper()
    if label == "US":
        return "USD"
    if len(label) == 3 and label.isalpha():
        return label
    return "USD"


def _availability(row: Mapping[str, Any]) -> str:
    explicit = _str(row, "availability").lower().replace(" ", "_")
    if explicit in _AVAIL_ENUM:
        return _AVAIL_ENUM[explicit]
    if explicit.upper() in _AVAIL_ENUM.values():
        return explicit.upper()
    raw_inv = row.get("库存", row.get("inventory", 0))
    try:
        inv = int(raw_inv) if raw_inv is not None and raw_inv != "" else 0
    except (TypeError, ValueError):
        inv = 0
    return "OUT_OF_STOCK" if inv <= 0 else "IN_STOCK"


def _condition(row: Mapping[str, Any]) -> str:
    raw = _str(row, "condition").lower().replace(" ", "_")
    if raw in _CONDITION_ENUM:
        return _CONDITION_ENUM[raw]
    if raw.upper() in _CONDITION_ENUM.values():
        return raw.upper()
    return "NEW"


def _identifier_exists_yes(row: Mapping[str, Any]) -> bool:
    val = _str(row, "identifier_exists").lower()
    return val in ("yes", "true", "1", "y")


def _price_payload(row: Mapping[str, Any], feed_label: str) -> Optional[dict]:
    amount = _price_amount(row)
    if amount is None:
        return None
    micros = int(round(amount * 1_000_000))
    return {
        "amountMicros": str(micros),
        "currencyCode": _currency(row, feed_label),
    }


def _shipping_weight(row: Mapping[str, Any]) -> Optional[dict]:
    """Parse '0.2 kg' / {value, unit} → Merchant ShippingWeight; omit if unparseable."""
    raw = row.get("shipping_weight")
    if raw is None or raw == "":
        return None
    if isinstance(raw, Mapping):
        try:
            value = float(raw.get("value"))
        except (TypeError, ValueError):
            return None
        unit = str(raw.get("unit") or "").strip()
        if not unit:
            return None
        return {"value": value, "unit": unit}
    text = str(raw).strip()
    if not text:
        return None
    m = re.match(
        r"^([+-]?\d+(?:\.\d+)?)\s*([a-zA-Z]+)$",
        text,
    )
    if not m:
        return None
    try:
        value = float(m.group(1))
    except ValueError:
        return None
    return {"value": value, "unit": m.group(2)}


def _set_if(attrs: MutableMapping[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return
    if isinstance(value, (list, tuple)) and not value:
        return
    attrs[key] = value


def map_row_to_product_input(
    row: Mapping[str, Any],
    *,
    channel: str = "online",
    content_language: str = "en",
    feed_label: str = "US",
) -> dict:
    """Convert one canonical feed row to a Merchant ProductInput-shaped dict.

    Uses ``productAttributes`` (REST ProductAttributes). ``channel`` is accepted
    for call-site compatibility; online → omit legacyLocal, else legacyLocal=True.
    """
    sku = _str(row, "SKU", "sku").replace(" ", "-")
    body: dict[str, Any] = {
        "offerId": sku,
        "contentLanguage": content_language,
        "feedLabel": feed_label,
    }
    if str(channel or "online").strip().lower() not in ("", "online"):
        body["legacyLocal"] = True

    attrs: dict[str, Any] = {}
    _set_if(attrs, "title", _str(row, "优化后标题", "标题", "title"))
    _set_if(attrs, "description", _str(row, "描述", "description"))
    _set_if(attrs, "link", _str(row, "链接", "link"))
    _set_if(attrs, "imageLink", _str(row, "图片链接", "image_link", "imageLink"))
    attrs["availability"] = _availability(row)
    attrs["condition"] = _condition(row)

    price = _price_payload(row, feed_label)
    if price is not None:
        attrs["price"] = price

    # Field contract: empty color → omit; never invent Multicolor.
    color = _str(row, "颜色", "color")
    _set_if(attrs, "color", color)

    size = _str(row, "尺码", "size")
    if size:
        attrs["sizes"] = [size]

    _set_if(attrs, "brand", _str(row, "品牌", "brand"))
    _set_if(attrs, "gender", _str(row, "gender"))
    _set_if(attrs, "ageGroup", _str(row, "age_group", "ageGroup"))
    _set_if(attrs, "material", _str(row, "材质", "material"))
    _set_if(attrs, "pattern", _str(row, "pattern"))
    _set_if(
        attrs,
        "googleProductCategory",
        _str(row, "GPC代码", "google_product_category", "googleProductCategory"),
    )
    _set_if(attrs, "itemGroupId", _str(row, "item_group_id", "itemGroupId"))
    _set_if(attrs, "sizeSystem", _str(row, "size_system", "sizeSystem"))
    _set_if(attrs, "sizeType", _str(row, "size_type", "sizeType"))
    _set_if(attrs, "mpn", _str(row, "mpn"))

    sw = _shipping_weight(row)
    if sw is not None:
        attrs["shippingWeight"] = sw

    # GTIN only when real value AND identifier_exists suggests yes — never invent.
    gtin = _str(row, "gtin", "GTIN")
    if gtin and _identifier_exists_yes(row):
        attrs["gtins"] = [gtin]

    body["productAttributes"] = attrs
    return body
