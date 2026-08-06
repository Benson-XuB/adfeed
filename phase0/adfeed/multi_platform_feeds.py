"""AdFeed AI — 多平台 Feed 生成器

支持从同一数据源生成不同平台的商品 Feed：
- Meta/Facebook Commerce Catalog（RSS XML，无 g: 前缀）
- TikTok Shop Product Catalog（CSV 格式）

数据层完全复用 pipeline.py 构建的 DataFrame。
"""

import csv
import json
import io
import html
from datetime import datetime, timezone
from pathlib import Path
from jinja2 import Template


# ─────────────────────────────────────────────────
# Meta/Facebook Commerce Catalog（RSS XML）
# ─────────────────────────────────────────────────

META_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>{{ shop_name }} - Product Catalog</title>
    <link>{{ site_link }}</link>
    <description>Product catalog for Meta Commerce | Generated {{ generated_at }}</description>
    {% for p in products %}
    <item>
      <id>{{ p.id }}</id>
      <title>{{ p.title }}</title>
      <description>{{ p.description }}</description>
      <link>{{ p.link }}</link>
      <image_link>{{ p.image_link }}</image_link>
      {% for img in p.additional_image_links %}<additional_image_link>{{ img }}</additional_image_link>
      {% endfor %}
      <price>{{ p.price }} {{ p.currency }}</price>
      {% if p.sale_price %}<sale_price>{{ p.sale_price }} {{ p.currency }}</sale_price>{% endif %}
      <availability>{{ p.availability }}</availability>
      <condition>{{ p.condition }}</condition>
      <brand>{{ p.brand }}</brand>
      <google_product_category>{{ p.google_product_category }}</google_product_category>
      {% if p.item_group_id %}<item_group_id>{{ p.item_group_id }}</item_group_id>{% endif %}
      {% if p.color %}<color>{{ p.color }}</color>{% endif %}
      {% if p.size %}<size>{{ p.size }}</size>{% endif %}
      {% if p.material %}<material>{{ p.material }}</material>{% endif %}
      {% if p.gender %}<gender>{{ p.gender }}</gender>{% endif %}
      {% if p.age_group %}<age_group>{{ p.age_group }}</age_group>{% endif %}
      {% if p.shipping_weight %}<shipping_weight>{{ p.shipping_weight }}</shipping_weight>{% endif %}
    </item>
    {% endfor %}
  </channel>
</rss>
"""


def generate_meta_feed(rows: list[dict], shop_name: str = "",
                       site_link: str = "", country: str = "US") -> str:
    """生成 Meta/Facebook Commerce Catalog XML

    与 Google Shopping 的区别：
    - 无 g: 命名空间前缀
    - 字段名直接（id 而非 g:id）
    - 支持 sale_price（促销价）
    - 无 shipping/tax 等 Google 专属字段

    Args:
        rows: pipeline 构建的行数据（与 Google Feed 相同的 dict 列表）
        shop_name: 店铺名称
        site_link: 网站链接
        country: 目标国家（用于汇率转换）

    Returns:
        XML 字符串
    """
    from .feed_generator import CURRENCY_MAP, EXCHANGE_RATES

    target_currency = CURRENCY_MAP.get(country.upper(), "USD")
    rate = EXCHANGE_RATES.get(target_currency, 1.0)

    products = []
    for row in rows:
        # 反转义 HTML 实体（Meta 不需要 XML 转义在标签内容中）
        def unesc(val):
            if not val:
                return ""
            return html.unescape(str(val))

        # 解析附加图片
        additional_images_raw = str(row.get("附加图片", ""))
        additional_links = []
        if additional_images_raw and additional_images_raw != "nan":
            try:
                img_list = json.loads(additional_images_raw)
                if isinstance(img_list, list):
                    additional_links = [unesc(img) for img in img_list if img]
            except (json.JSONDecodeError, TypeError):
                additional_links = [unesc(u.strip()) for u in additional_images_raw.split(",") if u.strip()]

        # 汇率转换
        orig_price = float(row.get('价格', 0))
        converted_price = round(orig_price * rate, 2)

        products.append({
            "id": unesc(row.get("SKU", "")),
            "title": unesc(row.get("优化后标题", row.get("标题", ""))),
            "description": unesc(row.get("描述", "")),
            "link": unesc(row.get("链接", "")),
            "image_link": unesc(row.get("图片链接", "")),
            "additional_image_links": additional_links,
            "price": f"{converted_price:.2f}",
            "currency": target_currency,
            "sale_price": f"{float(row.get('sale_price', 0)):.2f}" if float(row.get("sale_price", 0) or 0) > 0 else "",
            "availability": "in stock" if int(row.get("库存", 0) or 0) > 0 else "out of stock",
            "condition": "new",
            "brand": unesc(row.get("品牌", "")),
            "google_product_category": str(row.get("GPC代码", "")),
            "item_group_id": str(row.get("item_group_id", "")),
            "color": unesc(row.get("颜色", "")),
            "size": unesc(row.get("尺码", "")),
            "material": unesc(row.get("材质", "")),
            "gender": str(row.get("gender", "")),
            "age_group": str(row.get("age_group", "adult")),
            "shipping_weight": "",
        })

    return Template(META_XML_TEMPLATE, autoescape=True).render(
        products=products,
        shop_name=shop_name or "Store",
        site_link=site_link,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ─────────────────────────────────────────────────
# TikTok Shop Product Catalog（CSV）
# ─────────────────────────────────────────────────

# TikTok Shop CSV 表头
TIKTOK_CSV_FIELDS = [
    "Product ID",
    "Product Name",
    "Description",
    "Brand",
    "Category",
    "Variant ID",
    "Variant Name",
    "Price",
    "Sale Price",
    "Stock",
    "Status",
    "Main Image",
    "Additional Images",
    "Weight (kg)",
    "Package Length (cm)",
    "Package Width (cm)",
    "Package Height (cm)",
    "Color",
    "Size",
    "Gender",
    "Material",
]

# GPC → TikTok 品类映射（常见服饰品类）
_GPC_TO_TIKTOK_CATEGORY = {
    "4174": "Women's Clothing > Dresses",
    "2271": "Women's Clothing > Tops",
    "209": "Women's Clothing > Jeans",
    "5423": "Women's Clothing > Jackets & Coats",
    "5598": "Women's Clothing > Sweaters",
    "6228": "Women's Clothing > Skirts",
    "3913": "Women's Clothing > Pants",
    "207": "Women's Clothing > Shirts & Blouses",
    "502999": "Women's Clothing > Jumpsuits & Rompers",
    "3032": "Socks & Hosiery",
    "2923": "Socks & Hosiery",
}


def _gpc_to_tiktok_category(gpc_code: str, gpc_path: str = "") -> str:
    """GPC 代码 → TikTok 品类路径"""
    if gpc_code in _GPC_TO_TIKTOK_CATEGORY:
        return _GPC_TO_TIKTOK_CATEGORY[gpc_code]
    # 尝试从 GPC 路径推断
    if gpc_path:
        return gpc_path
    return "General"


def _estimate_weight(gpc_path: str) -> float:
    """根据品类估算包裹重量（kg）"""
    path_lower = gpc_path.lower() if gpc_path else ""
    if any(k in path_lower for k in ["coat", "jacket", "outerwear"]):
        return 0.8
    elif any(k in path_lower for k in ["jean", "pant", "dress"]):
        return 0.4
    elif any(k in path_lower for k in ["shirt", "top", "blouse"]):
        return 0.25
    elif any(k in path_lower for k in ["sock", "underwear"]):
        return 0.1
    elif any(k in path_lower for k in ["jumpsuit", "romper"]):
        return 0.35
    return 0.3  # 默认


def generate_tiktok_feed(rows: list[dict], shop_name: str = "") -> str:
    """生成 TikTok Shop Product Catalog CSV

    TikTok Shop 使用 CSV 批量上传格式，与 Google Shopping 的区别：
    - CSV 格式（非 XML）
    - 使用 TikTok 自己的品类树
    - 需要物流字段（weight/package_size）
    - 无 link 字段（TikTok 内部生成链接）
    - Variant 结构（Product ID + Variant ID）

    Args:
        rows: pipeline 构建的行数据
        shop_name: 店铺名称

    Returns:
        CSV 字符串
    """
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=TIKTOK_CSV_FIELDS,
                            extrasaction='ignore')
    writer.writeheader()

    # 按 item_group_id 分组（同一产品的不同变体）
    product_groups: dict[str, list[dict]] = {}
    for row in rows:
        group_id = str(row.get("item_group_id", row.get("SKU", "")))
        if group_id not in product_groups:
            product_groups[group_id] = []
        product_groups[group_id].append(row)

    for group_id, variants in product_groups.items():
        first = variants[0]
        product_name = str(first.get("优化后标题", first.get("标题", "")))
        description = html.unescape(str(first.get("描述", "")))
        brand = str(first.get("品牌", ""))
        category = _gpc_to_tiktok_category(
            str(first.get("GPC代码", "")),
            str(first.get("GPC路径", "")),
        )
        main_image = str(first.get("图片链接", ""))

        # 收集所有附加图片（跨变体去重）
        all_additional = []
        seen_imgs = {main_image}
        for v in variants:
            raw = str(v.get("附加图片", ""))
            if raw and raw != "nan":
                try:
                    imgs = json.loads(raw)
                    if isinstance(imgs, list):
                        for img in imgs:
                            if img and img not in seen_imgs:
                                all_additional.append(img)
                                seen_imgs.add(img)
                except (json.JSONDecodeError, TypeError):
                    for img in raw.split(","):
                        img = img.strip()
                        if img and img not in seen_imgs:
                            all_additional.append(img)
                            seen_imgs.add(img)

        additional_images = ";".join(all_additional[:5])  # TikTok 最多 9 张
        weight = _estimate_weight(str(first.get("GPC路径", "")))

        for v in variants:
            variant_id = str(v.get("SKU", ""))
            color = str(v.get("颜色", ""))
            size = str(v.get("尺码", ""))

            # Variant Name = Color + Size
            variant_parts = []
            if color:
                variant_parts.append(color)
            if size:
                variant_parts.append(size)
            variant_name = " - ".join(variant_parts) if variant_parts else variant_id

            price = float(v.get("价格", 0))
            stock = int(v.get("库存", 0))
            status = "Active" if stock > 0 else "Inactive"

            writer.writerow({
                "Product ID": group_id,
                "Product Name": html.unescape(product_name),
                "Description": description,
                "Brand": brand,
                "Category": category,
                "Variant ID": variant_id,
                "Variant Name": variant_name,
                "Price": f"{price:.2f}",
                "Sale Price": "",
                "Stock": stock,
                "Status": status,
                "Main Image": main_image,
                "Additional Images": additional_images,
                "Weight (kg)": f"{weight:.2f}",
                "Package Length (cm)": "30",
                "Package Width (cm)": "20",
                "Package Height (cm)": "5",
                "Color": color,
                "Size": size,
                "Gender": str(v.get("gender", "")),
                "Material": str(v.get("材质", "")),
            })

    return output.getvalue()


# ─────────────────────────────────────────────────
# 统一输出接口
# ─────────────────────────────────────────────────

def save_meta_feed(rows: list[dict], output_path: Path,
                   shop_name: str = "", site_link: str = "", country: str = "US"):
    """保存 Meta Commerce Feed XML"""
    xml = generate_meta_feed(rows, shop_name, site_link, country)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding="utf-8")
    item_count = xml.count("<item>")
    print(f"  [Meta] Feed: {item_count} items → {output_path}")
    return item_count


def save_tiktok_feed(rows: list[dict], output_path: Path,
                     shop_name: str = ""):
    """保存 TikTok Shop Feed CSV"""
    csv_content = generate_tiktok_feed(rows, shop_name)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(csv_content, encoding="utf-8")
    item_count = csv_content.count("\n") - 1  # 减去表头
    print(f"  [TikTok] Feed: {item_count} items → {output_path}")
    return item_count


def durable_feed_path(feeds_dir: Path, store_id: str, platform: str, language: str) -> Path:
    """FEEDS_DIR/{store_id}/{platform}/{lang}.{xml|csv}"""
    plat = platform.lower()
    lang = language.lower()
    ext = "csv" if plat == "tiktok" else "xml"
    return feeds_dir / store_id / plat / f"{lang}.{ext}"


def durable_feed_url(public_base: str, store_id: str, platform: str, language: str) -> str:
    plat = platform.lower()
    lang = language.lower()
    ext = "csv" if plat == "tiktok" else "xml"
    return f"{public_base.rstrip('/')}/feeds/{store_id}/{plat}/{lang}.{ext}"
