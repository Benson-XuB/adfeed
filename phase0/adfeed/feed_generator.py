"""AdFeed AI — Feed XML 生成器 v2.1（多国原生语种版本）

- 静态模式：从 DataFrame 生成（兼容旧接口 + pipeline 内调用）
- 动态模式：从 PRODUCT_MEMORY_DB 实时查询 → 每个国家取对应语种标题
- Inventory 熔断：inventory==0 自动 out_of_stock
- 多国币种自动转换
"""

import pandas as pd
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from jinja2 import Template

FEED_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:g="http://base.google.com/ns/1.0" version="2.0">
  <channel>
    <title>AdFeed AI - {{ country_name }} Feed</title>
    <link>{{ site_link }}</link>
    <description>AI-optimized product feed for Google Shopping | {{ country_name }} | Generated {{ generated_at }}</description>
    {% for p in products %}
    <item>
      <!-- 基础标识 -->
      <g:id>{{ p.sku }}</g:id>
      <g:title>{{ p.optimized_title | e }}</g:title>
      <g:description>{{ p.description | e }}</g:description>
      <g:link>{{ p.link | e }}</g:link>
      <g:image_link>{{ p.image_url | e }}</g:image_link>
      {% if p.additional_image_links %}{% for img in p.additional_image_links %}<g:additional_image_link>{{ img | e }}</g:additional_image_link>{% endfor %}{% endif %}
      <!-- 价格与库存 -->
      <g:price>{{ p.price }} {{ p.currency }}</g:price>
      {% if p.sale_price %}<g:sale_price>{{ p.sale_price }} {{ p.currency }}</g:sale_price>{% endif %}
      {% if p.sale_price_effective_date %}<g:sale_price_effective_date>{{ p.sale_price_effective_date }}</g:sale_price_effective_date>{% endif %}
      <g:availability>{{ p.availability }}</g:availability>
      <g:condition>new</g:condition>
      <!-- 产品标识 -->
      <g:identifier_exists>{{ p.identifier_exists }}</g:identifier_exists>
      {% if p.gtin %}<g:gtin>{{ p.gtin }}</g:gtin>{% endif %}
      {% if p.mpn %}<g:mpn>{{ p.mpn }}</g:mpn>{% endif %}
      {% if p.brand %}<g:brand>{{ p.brand | e }}</g:brand>{% endif %}
      <!-- 品类 -->
      {% if p.gpc_code %}<g:google_product_category>{{ p.gpc_code }}</g:google_product_category>{% endif %}
      {% if p.gpc_path %}<g:product_type>{{ p.gpc_path | e }}</g:product_type>{% endif %}
      <!-- 变体分组 -->
      {% if p.item_group_id %}<g:item_group_id>{{ p.item_group_id }}</g:item_group_id>{% endif %}
      {% if p.size %}<g:size>{{ p.size | e }}</g:size>{% endif %}
      {% if p.size_system %}<g:size_system>{{ p.size_system }}</g:size_system>{% endif %}
      {% if p.size_type %}<g:size_type>{{ p.size_type }}</g:size_type>{% endif %}
      {% if p.gender %}<g:gender>{{ p.gender }}</g:gender>{% endif %}
      {% if p.age_group %}<g:age_group>{{ p.age_group }}</g:age_group>{% endif %}
      {% if p.color %}<g:color>{{ p.color | e }}</g:color>{% endif %}
      {% if p.material %}<g:material>{{ p.material | e }}</g:material>{% endif %}
      <!-- 活动分层 -->
      {% if p.custom_label_0 %}<g:custom_label_0>{{ p.custom_label_0 | e }}</g:custom_label_0>{% endif %}
      {% if p.custom_label_1 %}<g:custom_label_1>{{ p.custom_label_1 | e }}</g:custom_label_1>{% endif %}
      {% if p.custom_label_2 %}<g:custom_label_2>{{ p.custom_label_2 | e }}</g:custom_label_2>{% endif %}
      {% if p.custom_label_3 %}<g:custom_label_3>{{ p.custom_label_3 | e }}</g:custom_label_3>{% endif %}
      {% if p.custom_label_4 %}<g:custom_label_4>{{ p.custom_label_4 | e }}</g:custom_label_4>{% endif %}
      <!-- 物流 -->
      {% if p.shipping %}<g:shipping><g:country>{{ p.shipping_country | e }}</g:country><g:service>Standard</g:service><g:price>{{ p.shipping_price }} {{ p.currency }}</g:price></g:shipping>{% endif %}
      {% if p.shipping_weight %}<g:shipping_weight>{{ p.shipping_weight }}</g:shipping_weight>{% endif %}
      {% if p.min_handling_time > 0 %}<g:min_handling_time>{{ p.min_handling_time }}</g:min_handling_time>{% endif %}
      {% if p.max_handling_time > 0 %}<g:max_handling_time>{{ p.max_handling_time }}</g:max_handling_time>{% endif %}
      <!-- 合规 -->
      <g:adult>{{ p.adult }}</g:adult>
      {% if p.multipack > 0 %}<g:multipack>{{ p.multipack }}</g:multipack>{% endif %}
      {% if p.is_bundle == 'yes' %}<g:is_bundle>yes</g:is_bundle>{% endif %}
      {% if p.tax %}<g:tax><g:country>{{ p.shipping_country | e }}</g:country><g:rate>{{ p.tax }}</g:rate><g:tax_ship>no</g:tax_ship></g:tax>{% endif %}
      {% if p.energy_efficiency_class %}<g:energy_efficiency_class>{{ p.energy_efficiency_class }}</g:energy_efficiency_class>{% endif %}
      {% if p.unit_pricing_measure %}<g:unit_pricing_measure>{{ p.unit_pricing_measure }}</g:unit_pricing_measure>{% endif %}
      {% if p.unit_pricing_base_measure %}<g:unit_pricing_base_measure>{{ p.unit_pricing_base_measure }}</g:unit_pricing_base_measure>{% endif %}
      <!-- JSON-LD structured data for AI search engines -->
      {{ p.jsonld }}
    </item>
    {% endfor %}
  </channel>
</rss>
"""

CURRENCY_MAP = {"US": "USD", "DE": "EUR", "FR": "EUR", "ES": "EUR", "IT": "EUR"}
_USD_EUR_RATE = float(os.getenv("ADFEED_USD_EUR",  "0.92"))
EXCHANGE_RATES = {"USD": 1.0, "EUR": _USD_EUR_RATE}


def _build_jsonld(sku: str, title: str, description: str, row: dict,
                  price: float, currency: str, availability: str) -> str:
    """Build JSON-LD structured data block for AI search engine consumption (AEO)."""
    avail = ("https://schema.org/InStock" if availability == "in_stock"
             else "https://schema.org/LimitedAvailability" if availability == "limited_availability"
             else "https://schema.org/OutOfStock")

    ll = {
        "@context": "https://schema.org/",
        "@type": "Product",
        "sku": sku,
        "name": title,
        "description": description,
        "image": row.get("image_url", ""),
        "offers": {
            "@type": "Offer",
            "price": f"{price:.2f}",
            "priceCurrency": currency,
            "availability": avail,
        },
    }
    if row.get("color"):
        ll["color"] = row["color"]
    if row.get("material"):
        ll["material"] = row["material"]
    if row.get("size"):
        ll["size"] = row["size"]
    if row.get("gender") and row["gender"] not in ("", "unisex"):
        ll["gender"] = row.get("gender")
    if row.get("age_group") and row["age_group"] != "adult":
        ll["audience"] = {"@type": "PeopleAudience", "suggestedAge": {"@type": "QuantitativeValue", "name": row["age_group"]}}
    if row.get("gpc_path"):
        ll["category"] = row["gpc_path"]
    if row.get("brand"):
        ll["brand"] = {"@type": "Brand", "name": row["brand"]}
    if row.get("gtin"):
        ll["gtin"] = row["gtin"]
    if row.get("mpn"):
        ll["mpn"] = row["mpn"]
    if row.get("ai_tags"):
        try:
            tags = json.loads(row["ai_tags"]) if isinstance(row["ai_tags"], str) else row["ai_tags"]
            ll["keywords"] = ", ".join(tags)
        except (json.JSONDecodeError, TypeError):
            pass

    return f"<script type=\"application/ld+json\">\n{json.dumps(ll, ensure_ascii=False, indent=2)}\n  </script>"


def _convert_price(price_usd: float, country: str):
    currency = CURRENCY_MAP.get(country.upper(), "USD")
    rate = EXCHANGE_RATES.get(currency, 1.0)
    return round(price_usd * rate, 2), currency


def _country_display(country: str) -> str:
    names = {"US": "United States", "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy"}
    return names.get(country.upper(), country.upper())


# ─────────────────────────────────────────────
# 静态模式：从 DataFrame 生成
# ─────────────────────────────────────────────

def generate(df: pd.DataFrame, country: str = "US", site_link: str = "https://adfeed.ai") -> str:
    products = []
    for _, row in df.iterrows():
        price_str = str(row.get("价格", "0.00"))
        try:
            price_val = float(price_str.replace("USD", "").replace("EUR", "").strip())
        except (ValueError, AttributeError):
            price_val = 0.0
        price, currency = _convert_price(price_val, country)
        inv = int(row.get("库存", row.get("inventory", 1)) or 1)

        products.append({
            "sku": str(row.get("SKU", "")),
            "optimized_title": str(row.get("优化后标题", row.get("标题", ""))),
            "description": str(row.get("description_snippet", row.get("描述", ""))),
            "link": str(row.get("链接", f"https://example.com/product/{row.get('SKU', '')}")),
            "image_url": str(row.get("图片链接", "")),
            "additional_image_links": [],
            "price": f"{price:.2f}",
            "currency": currency,
            "sale_price": "",
            "sale_price_effective_date": "",
            "availability": "out_of_stock" if inv <= 0 else ("limited_availability" if inv < 5 else "in_stock"),
            "identifier_exists": str(row.get("identifier_exists", "no")),
            "gtin": str(row.get("gtin", "")),
            "mpn": str(row.get("mpn", "")),
            "gpc_code": str(row.get("GPC代码", "")),
            "gpc_path": str(row.get("GPC路径", "")),
            "brand": str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else "",
            "item_group_id": str(row.get("item_group_id", "")),
            "color": str(row.get("颜色", "")) if pd.notna(row.get("颜色")) else "",
            "material": str(row.get("材质", "")) if pd.notna(row.get("材质")) else "",
            "size": str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else "",
            "size_system": str(row.get("size_system", "")),
            "size_type": str(row.get("size_type", "")),
            "gender": str(row.get("gender", "")),
            "age_group": str(row.get("age_group", "adult")),
            "custom_label_0": str(row.get("custom_label_0", "")),
            "custom_label_1": str(row.get("custom_label_1", "")),
            "custom_label_2": str(row.get("custom_label_2", "")),
            "custom_label_3": str(row.get("custom_label_3", "")),
            "custom_label_4": str(row.get("custom_label_4", "")),
            "shipping": False,
            "shipping_country": str(row.get("shipping_country", "")),
            "shipping_price": str(row.get("shipping_price", "0")),
            "shipping_weight": str(row.get("shipping_weight", "")),
            "min_handling_time": int(row.get("min_handling_time", 0) or 0),
            "max_handling_time": int(row.get("max_handling_time", 0) or 0),
            "adult": str(row.get("adult", "no")),
            "multipack": int(row.get("multipack", 0) or 0),
            "is_bundle": str(row.get("is_bundle", "no")),
            "tax": str(row.get("tax", "")),
            "energy_efficiency_class": str(row.get("energy_efficiency_class", "")),
            "unit_pricing_measure": str(row.get("unit_pricing_measure", "")),
            "unit_pricing_base_measure": str(row.get("unit_pricing_base_measure", "")),
        })

    return Template(FEED_XML_TEMPLATE, autoescape=True).render(
        products=products, country_name=_country_display(country),
        site_link=site_link, generated_at=datetime.now(timezone.utc).isoformat(),
    )


def save(df: pd.DataFrame, path: Path, country: str = "US"):
    path.parent.mkdir(parents=True, exist_ok=True)
    xml = generate(df, country)
    path.write_text(xml, encoding="utf-8")
    print(f"[FeedGen] {path.name} ({len(df)} SKU, {len(xml.encode('utf-8')):,} bytes)")


# ─────────────────────────────────────────────
# 动态模式：从 PRODUCT_MEMORY_DB 生成（多国语版本）
# ─────────────────────────────────────────────

def generate_from_memory(
    target_country: str = "US",
    site_link: str = "https://adfeed.ai",
    user_id: str = None,
):
    """从 PRODUCT_MEMORY_DB 动态生成指定国家的 Feed XML"""
    from .product_memory import get_all_active

    all_products = get_all_active(target_country=target_country)

    products = []
    in_stock_count = 0
    out_of_stock_count = 0

    for p in all_products:
        inventory = int(p.get("inventory", 0))
        price_usd = float(p.get("price_usd", 0))
        price, currency = _convert_price(price_usd, target_country)

        availability = ("out_of_stock" if inventory <= 0
                        else "limited_availability" if inventory < 5
                        else "in_stock")

        if inventory <= 0:
            out_of_stock_count += 1
        else:
            in_stock_count += 1

        titles = p.get("optimized_titles", {})
        snippets = p.get("description_snippets", {})

        optimized_title = titles.get(target_country.upper(), 
                                     titles.get("US", p.get("original_title", "")))
        description = snippets.get(target_country.upper(),
                                   snippets.get("US", p.get("description", "")))

        # 附加图片
        additional = p.get("additional_images", "")
        additional_links = [u.strip() for u in additional.split(",") if u.strip()] if additional else []

        products.append({
            "sku": p.get("product_id", ""),
            "optimized_title": _safe_str(optimized_title, "Product"),
            "description": _safe_str(description, ""),
            "link": f"{site_link}/product/{p.get('product_id', '')}",
            "image_url": _safe_str(p.get("image_url", ""), ""),
            "additional_image_links": additional_links,
            "price": f"{price:.2f}",
            "currency": currency,
            "sale_price": f"{sale_price:.2f}" if (sale_price := float(p.get("sale_price_usd", 0) or 0)) > 0 else "",
            "sale_price_effective_date": p.get("sale_price_effective_date", ""),
            "availability": availability,
            "identifier_exists": p.get("identifier_exists", "no"),
            "gtin": p.get("gtin", ""),
            "mpn": p.get("mpn", ""),
            "gpc_code": p.get("gpc_code", ""),
            "gpc_path": p.get("gpc_path", ""),
            "brand": p.get("brand", ""),
            "item_group_id": p.get("item_group_id", ""),
            "color": p.get("color", ""),
            "material": p.get("material", ""),
            "size": p.get("size", ""),
            "size_system": p.get("size_system", ""),
            "size_type": p.get("size_type", ""),
            "gender": p.get("gender", ""),
            "age_group": p.get("age_group", "adult"),
            "custom_label_0": p.get("custom_label_0", ""),
            "custom_label_1": p.get("custom_label_1", ""),
            "custom_label_2": p.get("custom_label_2", ""),
            "custom_label_3": p.get("custom_label_3", ""),
            "custom_label_4": p.get("custom_label_4", ""),
            "shipping": bool(p.get("shipping_country", "") and float(p.get("shipping_price", 0) or 0) > 0),
            "shipping_country": p.get("shipping_country", ""),
            "shipping_price": f"{float(p.get('shipping_price', 0) or 0):.2f}",
            "shipping_weight": p.get("shipping_weight", ""),
            "min_handling_time": int(p.get("min_handling_time", 0) or 0),
            "max_handling_time": int(p.get("max_handling_time", 0) or 0),
            "adult": p.get("adult", "no"),
            "multipack": int(p.get("multipack", 0) or 0),
            "is_bundle": p.get("is_bundle", "no"),
            "tax": p.get("tax", ""),
            "energy_efficiency_class": p.get("energy_efficiency_class", ""),
            "unit_pricing_measure": p.get("unit_pricing_measure", ""),
            "unit_pricing_base_measure": p.get("unit_pricing_base_measure", ""),
            "jsonld": _build_jsonld(sku, optimized_title, description, p, price, currency, availability),
        })

    xml = Template(FEED_XML_TEMPLATE, autoescape=True).render(
        products=products,
        country_name=_country_display(target_country),
        site_link=site_link,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    stats = {
        "total_products": len(all_products),
        "in_stock": in_stock_count,
        "out_of_stock": out_of_stock_count,
        "country": target_country,
        "file_size_bytes": len(xml.encode("utf-8")),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    return xml, stats


def _safe_str(val, default: str = "") -> str:
    if val is None:
        return default
    try:
        if isinstance(val, float) and (val != val):
            return default
    except Exception:
        pass
    return str(val)


# ─────────────────────────────────────────────
# 对比报告
# ─────────────────────────────────────────────

def generate_comparison_report(df: pd.DataFrame, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    print(f"[FeedGen] Comparison report: {path}")
