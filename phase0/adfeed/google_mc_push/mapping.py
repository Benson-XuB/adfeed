"""Map AdFeed feed rows → Merchant API ProductInput bodies.

Does not invent GTIN / brand / title polish — field contract.
"""

from __future__ import annotations

from typing import Any, Optional


def _pick(row: dict[str, Any], *keys: str, default: str = "") -> str:
    for k in keys:
        if k not in row:
            continue
        v = row.get(k)
        if v is None:
            continue
        s = str(v).strip()
        if s and s.lower() != "nan":
            return s
    return default


def _price_micros(price_raw: str, currency_hint: str = "") -> Optional[dict[str, str]]:
    """Parse '19.99' or '19.99 USD' into Merchant price object."""
    text = (price_raw or "").strip()
    if not text:
        return None
    parts = text.split()
    amount_s = parts[0]
    currency = (parts[1] if len(parts) > 1 else currency_hint or "USD").upper()
    try:
        amount = float(amount_s.replace(",", ""))
    except ValueError:
        return None
    micros = str(int(round(amount * 1_000_000)))
    return {"amountMicros": micros, "currencyCode": currency}


def _availability(raw: str) -> str:
    v = (raw or "").strip().lower().replace("-", "_")
    if v in ("out_of_stock", "outofstock", "out of stock"):
        return "OUT_OF_STOCK"
    if v in ("preorder", "pre_order"):
        return "PREORDER"
    if v in ("backorder", "back_order"):
        return "BACKORDER"
    return "IN_STOCK"


def _condition(raw: str) -> str:
    v = (raw or "new").strip().lower()
    if v == "refurbished":
        return "REFURBISHED"
    if v == "used":
        return "USED"
    return "NEW"


def _identifier_exists(raw: str) -> bool:
    v = (raw or "no").strip().lower()
    return v in ("yes", "true", "1", "y")


def feed_row_to_product_input(
    row: dict[str, Any],
    *,
    content_language: str = "en",
    feed_label: str = "US",
) -> dict[str, Any]:
    """Build a ProductInput dict for productInputs.insert.

    Accepts both rendered feed product_data keys (sku, image_url, link, …)
    and a few aliases used in tests / CSV-ish rows (title, 链接, image_link).
    """
    offer_id = _pick(row, "sku", "SKU", "id", "g:id")
    if not offer_id:
        raise ValueError("feed row missing sku/offerId")

    title = _pick(row, "optimized_title", "title", "优化后标题", "标题")
    description = _pick(row, "description", "描述")
    link = _pick(row, "link", "链接")
    image = _pick(row, "image_url", "image_link", "图片链接")
    brand = _pick(row, "brand", "品牌")
    color = _pick(row, "color", "颜色")
    size = _pick(row, "size", "尺码")
    pattern = _pick(row, "pattern")
    material = _pick(row, "material", "材质")
    item_group = _pick(row, "item_group_id")
    gtin = _pick(row, "gtin", "GTIN")
    currency = _pick(row, "currency", default="USD")
    price_raw = _pick(row, "price")
    if price_raw and " " not in price_raw and currency:
        # product_data stores price + currency separately
        pass
    price_obj = _price_micros(
        f"{price_raw} {currency}".strip() if price_raw and currency and " " not in price_raw else price_raw,
        currency_hint=currency,
    )

    attrs: dict[str, Any] = {}
    if title:
        attrs["title"] = title
    if description:
        attrs["description"] = description
    if link:
        attrs["link"] = link
    if image:
        attrs["imageLink"] = image
    attrs["availability"] = _availability(_pick(row, "availability", default="in_stock"))
    attrs["condition"] = _condition(_pick(row, "condition", default="new"))
    if price_obj:
        attrs["price"] = price_obj
    if brand:
        attrs["brand"] = brand
    if color:
        attrs["color"] = color
    if size:
        attrs["sizes"] = [size]
    if pattern:
        attrs["pattern"] = pattern
    if material:
        attrs["materials"] = [material]
    if item_group:
        attrs["itemGroupId"] = item_group

    size_system = _pick(row, "size_system")
    if size_system:
        attrs["sizeSystem"] = size_system
    size_type = _pick(row, "size_type")
    if size_type:
        attrs["sizeTypes"] = [size_type]
    gender = _pick(row, "gender")
    if gender:
        attrs["gender"] = gender.upper() if gender.lower() in ("male", "female", "unisex") else gender
    age_group = _pick(row, "age_group")
    if age_group:
        attrs["ageGroup"] = age_group.upper() if age_group.isalpha() else age_group

    id_exists = _identifier_exists(_pick(row, "identifier_exists", default="no"))
    attrs["identifierExists"] = id_exists
    if gtin:
        # Only pass through real values already on the row — never invent.
        attrs["gtins"] = [gtin]

    return {
        "offerId": offer_id,
        "contentLanguage": content_language,
        "feedLabel": feed_label,
        "productAttributes": attrs,
    }
