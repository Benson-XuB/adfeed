"""AdFeed AI — 变体展开引擎 v1.0

将 Shopify/1688 的产品数据展开为 Google Shopping 要求的变体级别行。
- Shopify CSV: 每行已是 variant，直接映射
- 1688/店小秘 Excel: 产品级数据，需解析规格字段并笛卡尔积展开
- 输出: GMC-ready 的 variant 行列表，每行有独立 id/size/color/price/link

核心映射:
  Shopify 1行产品 → N 个 variants → Feed XML 中 N 行 <item>
  每个 variant 有独立的:
    <g:id> = SKU-RED-XL
    <g:link> = /products/handle?variant=123456
    <g:price> = 该 variant 的价格
    <g:size> = XL
    <g:color> = Red
    <g:item_group_id> = 同一产品所有 variant 共享
"""

import re
from typing import Optional
from itertools import product as cartesian_product


# ═══════════════════════════════════════════════════════════════
# Shopify CSV 列名映射（支持多语言导出）
# ═══════════════════════════════════════════════════════════════

SHOPIFY_VARIANT_COLUMNS = {
    "variant_id": ["Variant ID", "Variant SKU", "variant_id"],
    "variant_sku": ["Variant SKU", "Variant SKU", "variant_sku"],
    "variant_price": ["Variant Price", "Variant price", "Price", "variant_price"],
    "variant_inventory": [
        "Variant Inventory Qty", "Variant Inventory Policy",
        "Inventory Qty", "variant_inventory_quantity",
    ],
    "option1_name": ["Option1 Name", "Option 1 Name", "option1_name"],
    "option1_value": ["Option1 Value", "Option 1 Value", "option1_value"],
    "option2_name": ["Option2 Name", "Option 2 Name", "option2_name"],
    "option2_value": ["Option2 Value", "Option 2 Value", "option2_value"],
    "option3_name": ["Option3 Name", "Option 3 Name", "option3_name"],
    "option3_value": ["Option3 Value", "Option 3 Value", "option3_value"],
    "handle": ["Handle", "handle", "Slug"],
    "image_src": ["Image Src", "Image URL", "image_src"],
    "title": ["Title", "title", "标题"],
    "body_html": ["Body (HTML)", "Body HTML", "Description", "body_html", "描述"],
    "product_type": ["Product Category", "Type", "product_type", "分类"],
    "vendor": ["Vendor", "vendor", "品牌"],
    "tags": ["Tags", "tags"],
}


def _find_column(row: dict, candidates: list[str]) -> str:
    """在 row 中查找匹配的列名（忽略大小写），返回值或空字符串"""
    for col in candidates:
        for key in row:
            if key.lower().strip() == col.lower().strip():
                val = row[key]
                return str(val) if val is not None and str(val) != "nan" else ""
    return ""


def is_shopify_format(row: dict) -> bool:
    """检测是否为 Shopify 导出格式"""
    shopify_markers = ["Variant ID", "Variant SKU", "Option1 Name", "Option1 Value",
                       "Variant Price", "Handle", "Image Src"]
    row_keys_lower = {k.lower().strip() for k in row.keys()}
    return any(marker.lower() in row_keys_lower for marker in shopify_markers)


# ═══════════════════════════════════════════════════════════════
# 1688/店小秘 规格字段解析
# ═══════════════════════════════════════════════════════════════

def _parse_spec_string(spec: str) -> dict:
    """解析 1688/店小秘的规格字段

    支持格式:
      - "颜色:红色,蓝色;尺码:S,M,L"
      - "红色/S/M/L;蓝色/XL/XXL"
      - "红色,XL|蓝色,M"
      - "颜色 红色 蓝色 / 尺码 S M L"

    Returns:
        {"颜色": ["红色", "蓝色"], "尺码": ["S", "M", "L"]}
    """
    if not spec or not spec.strip():
        return {}

    result = {}
    spec = spec.strip()

    # 格式1: "颜色:红色,蓝色;尺码:S,M,L" 或 "颜色:红色/蓝色;尺码:S/M/L"
    if ":" in spec or "：" in spec:
        parts = re.split(r'[;；]', spec)
        for part in parts:
            part = part.strip()
            if not part:
                continue
            # 分割 key:value
            kv_match = re.match(r'([^:：]+)[:：](.+)', part)
            if kv_match:
                key = kv_match.group(1).strip()
                values_str = kv_match.group(2).strip()
                values = re.split(r'[,，/|]', values_str)
                values = [v.strip() for v in values if v.strip()]
                if values:
                    result[key] = values

    # 格式2: "红色/S/M/L;蓝色/XL/XXL" (无 key，按位置推断)
    elif "/" in spec:
        groups = re.split(r'[;；]', spec)
        if len(groups) == 1:
            # 单组: "红色/S/M/L" → 可能全是尺码
            values = [v.strip() for v in groups[0].split("/") if v.strip()]
            if values:
                result["规格"] = values
        else:
            # 多组: 第一组可能是颜色+尺码混合
            all_values = []
            for g in groups:
                vals = [v.strip() for v in g.split("/") if v.strip()]
                all_values.extend(vals)
            if all_values:
                result["规格"] = all_values

    # 格式3: "红色,XL|蓝色,M" (管道分隔的变体组合)
    elif "|" in spec:
        combos = [c.strip() for c in spec.split("|") if c.strip()]
        result["_combos"] = []
        for combo in combos:
            parts = [p.strip() for p in re.split(r'[,，]', combo) if p.strip()]
            if parts:
                result["_combos"].append(parts)

    # 格式4: 简单逗号分隔 "红色,蓝色,黑色"
    elif "," in spec or "，" in spec:
        values = re.split(r'[,，]', spec)
        values = [v.strip() for v in values if v.strip()]
        if values:
            result["规格"] = values

    return result


# ═══════════════════════════════════════════════════════════════
# 颜色/尺码关键词检测
# ═══════════════════════════════════════════════════════════════

_COLOR_KEYWORDS_CN = {
    "颜色", "色", "color", "colour", "farbe", "couleur", "colore", "color",
}
_SIZE_KEYWORDS_CN = {
    "尺码", "码", "尺寸", "size", "größe", "taille", "taglia", "talla",
}
_COLOR_VALUES_EN = {
    "red", "blue", "black", "white", "green", "yellow", "pink", "purple",
    "orange", "gray", "grey", "brown", "beige", "khaki", "navy", "camel",
    "burgundy", "gold", "silver", "clear", "transparent", "multicolor",
    "rose gold", "light blue", "dark blue", "sky blue", "army green",
}
_SIZE_VALUES_EN = {
    "xs", "s", "m", "l", "xl", "xxl", "xxxl", "2xl", "3xl", "4xl", "5xl",
    "one size", "free size",
}


def _classify_spec_key(key: str) -> str:
    """判断规格字段是颜色还是尺码"""
    key_lower = key.lower().strip()
    if key_lower in _COLOR_KEYWORDS_CN:
        return "color"
    if key_lower in _SIZE_KEYWORDS_CN:
        return "size"
    # 检查值是否像颜色或尺码
    return "unknown"


def _classify_spec_value(value: str) -> str:
    """判断规格值是颜色还是尺码"""
    v_lower = value.lower().strip()
    if v_lower in _COLOR_VALUES_EN:
        return "color"
    if v_lower in _SIZE_VALUES_EN:
        return "size"
    # 中文检测
    if re.search(r'[\u4e00-\u9fff]', value):
        # 可能是中文颜色名
        return "color"
    return "unknown"


# ═══════════════════════════════════════════════════════════════
# 核心: 变体展开
# ═══════════════════════════════════════════════════════════════

def expand_variants(row: dict) -> list[dict]:
    """将单行产品数据展开为变体级别的多行

    Args:
        row: 产品行数据（可以是 Shopify CSV 行或 1688 Excel 行）

    Returns:
        [
            {
                "variant_id": "SKU-RED-XL",
                "item_group_id": "SKU",
                "sku": "SKU",
                "size": "XL",
                "color": "Red",
                "price": 29.99,
                "inventory": 10,
                "image_url": "https://...",
                "link": "/products/handle?variant=123",
                ...原始字段保留
            },
            ...
        ]
    """
    if is_shopify_format(row):
        return _expand_shopify_variant(row)
    else:
        return _expand_generic_variant(row)


def _expand_shopify_variant(row: dict) -> list[dict]:
    """Shopify 格式: 每行已是一个 variant，直接映射"""
    variant_id = _find_column(row, SHOPIFY_VARIANT_COLUMNS["variant_id"])
    variant_sku = _find_column(row, SHOPIFY_VARIANT_COLUMNS["variant_sku"])
    price = _find_column(row, SHOPIFY_VARIANT_COLUMNS["variant_price"])
    inventory = _find_column(row, SHOPIFY_VARIANT_COLUMNS["variant_inventory"])
    handle = _find_column(row, SHOPIFY_VARIANT_COLUMNS["handle"])
    image_src = _find_column(row, SHOPIFY_VARIANT_COLUMNS["image_src"])

    # 提取 Option 值（颜色/尺码等）
    options = {}
    for i in range(1, 4):
        opt_name = _find_column(row, SHOPIFY_VARIANT_COLUMNS.get(f"option{i}_name", []))
        opt_value = _find_column(row, SHOPIFY_VARIANT_COLUMNS.get(f"option{i}_value", []))
        if opt_name and opt_value:
            opt_type = _classify_spec_key(opt_name)
            if opt_type == "color":
                options["color"] = opt_value
            elif opt_type == "size":
                options["size"] = opt_value
            else:
                # 根据值推断类型
                val_type = _classify_spec_value(opt_value)
                if val_type == "color":
                    options["color"] = opt_value
                elif val_type == "size":
                    options["size"] = opt_value
                else:
                    # 默认: option1=color, option2=size
                    if i == 1:
                        options["color"] = opt_value
                    elif i == 2:
                        options["size"] = opt_value

    # 构建 variant ID（避免 SKU 已包含颜色/尺码时重复追加）
    sku_base = variant_sku or variant_id or str(row.get("SKU", "SKU"))
    sku_lower = sku_base.lower()
    parts = [sku_base]
    color_val = options.get("color", "")
    size_val = options.get("size", "")
    if color_val and color_val.lower() not in sku_lower:
        parts.append(color_val.replace(" ", "-"))
    if size_val and size_val.lower() not in sku_lower:
        parts.append(size_val.replace(" ", "-"))
    variant_uid = "-".join(parts)

    # 构建 variant link
    if handle:
        variant_link = f"/products/{handle}"
        if variant_id:
            variant_link += f"?variant={variant_id}"
    else:
        variant_link = f"/products/{variant_uid}"

    try:
        price_val = float(price) if price else 0.0
    except (ValueError, TypeError):
        price_val = 0.0

    try:
        inv_val = int(float(inventory)) if inventory else 1
    except (ValueError, TypeError):
        inv_val = 1

    # item_group_id: 同一产品的所有 variant 共享
    # Shopify 用 Handle 作为产品级标识（所有 variant 共享同一个 Handle）
    product_group_id = handle or sku_base

    variant = dict(row)  # 保留原始字段
    variant.update({
        "variant_id": variant_uid,
        "item_group_id": product_group_id,
        "sku": sku_base,
        "SKU": variant_uid,
        "size": options.get("size", ""),
        "color": options.get("color", ""),
        "尺码": options.get("size", ""),
        "颜色": options.get("color", ""),
        "价格": price_val,
        "库存": inv_val,
        "图片链接": image_src,
        "链接": variant_link,
        "_shopify_variant_id": variant_id,
        "_shopify_handle": handle,
    })
    return [variant]


def _expand_generic_variant(row: dict) -> list[dict]:
    """1688/通用格式: 解析规格字段并展开为笛卡尔积"""
    sku = str(row.get("SKU", row.get("sku", "SKU")))
    title = str(row.get("标题", row.get("title", "")))
    price_raw = row.get("价格", row.get("price", 0))
    inv_raw = row.get("库存", row.get("inventory", 1))

    try:
        price_val = float(price_raw) if price_raw else 0.0
    except (ValueError, TypeError):
        price_val = 0.0

    try:
        inv_val = int(float(inv_raw)) if inv_raw else 1
    except (ValueError, TypeError):
        inv_val = 1

    # 先检查是否已有独立的颜色/尺码字段
    existing_color = str(row.get("颜色", row.get("color", ""))).strip()
    existing_size = str(row.get("尺码", row.get("size", ""))).strip()

    # 解析规格字段
    spec_raw = str(row.get("规格", row.get("specification", row.get("specs", "")))).strip()
    parsed = _parse_spec_string(spec_raw) if spec_raw else {}

    # 提取颜色列表和尺码列表
    colors = []
    sizes = []

    # 从解析结果中提取
    for key, values in parsed.items():
        if key == "_combos":
            continue
        key_type = _classify_spec_key(key)
        if key_type == "color":
            colors.extend(values)
        elif key_type == "size":
            sizes.extend(values)
        else:
            # 根据值推断
            for v in values:
                v_type = _classify_spec_value(v)
                if v_type == "color":
                    colors.append(v)
                elif v_type == "size":
                    sizes.append(v)

    # 处理 _combos 格式
    if "_combos" in parsed:
        for combo in parsed["_combos"]:
            for val in combo:
                v_type = _classify_spec_value(val)
                if v_type == "color" and val not in colors:
                    colors.append(val)
                elif v_type == "size" and val not in sizes:
                    sizes.append(val)

    # 去重
    colors = list(dict.fromkeys(c for c in colors if c))
    sizes = list(dict.fromkeys(s for s in sizes if s))

    # 如果已有独立字段，优先使用
    if existing_color and not colors:
        colors = [existing_color]
    if existing_size and not sizes:
        sizes = [existing_size]

    # 如果都没有 → 单 variant（无规格展开）
    if not colors and not sizes:
        variant = dict(row)
        variant["variant_id"] = sku
        variant["item_group_id"] = sku
        variant["SKU"] = sku
        variant["价格"] = price_val
        variant["库存"] = inv_val
        return [variant]

    # 笛卡尔积展开（颜色×尺码）
    variants = []
    all_colors = colors if colors else [""]
    all_sizes = sizes if sizes else [""]

    for color, size in cartesian_product(all_colors, all_sizes):
        if not color and not size:
            continue

        # 构建 variant ID: SKU-颜色-尺码
        parts = [sku]
        if color:
            parts.append(color.replace(" ", "-"))
        if size:
            parts.append(size.replace(" ", "-"))
        variant_uid = "-".join(parts)

        # 库存均分给各 variant
        total_variants = len(all_colors) * len(all_sizes)
        per_variant_inv = max(1, inv_val // total_variants)

        variant = dict(row)
        variant.update({
            "variant_id": variant_uid,
            "item_group_id": sku,
            "SKU": variant_uid,
            "颜色": color,
            "尺码": size,
            "size": size,
            "color": color,
            "价格": price_val,
            "库存": per_variant_inv,
        })
        variants.append(variant)

    return variants if variants else [dict(row)]


def expand_all_variants(rows: list[dict]) -> list[dict]:
    """批量展开所有产品的变体

    Args:
        rows: 产品行列表

    Returns:
        展开后的变体行列表（扁平化）
    """
    all_variants = []
    for row in rows:
        variants = expand_variants(row)
        all_variants.extend(variants)
    return all_variants
