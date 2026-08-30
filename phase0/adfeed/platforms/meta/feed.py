"""Meta Commerce Catalog feed export."""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Template

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


def generate_meta_feed(
    rows: list[dict],
    shop_name: str = "",
    site_link: str = "",
    country: str = "US",
) -> str:
    from adfeed.market_pricing import expected_currency_for_country

    target_currency = expected_currency_for_country(country)
    products = []
    for row in rows:

        def unesc(val):
            if not val:
                return ""
            return html.unescape(str(val))

        additional_images_raw = str(row.get("附加图片", ""))
        additional_links = []
        if additional_images_raw and additional_images_raw != "nan":
            try:
                img_list = json.loads(additional_images_raw)
                if isinstance(img_list, list):
                    additional_links = [unesc(img) for img in img_list if img]
            except (json.JSONDecodeError, TypeError):
                additional_links = [
                    unesc(u.strip()) for u in additional_images_raw.split(",") if u.strip()
                ]

        try:
            price_amount = float(row.get("价格", 0) or 0)
        except (TypeError, ValueError):
            price_amount = 0.0
        row_ccy = str(row.get("_feed_currency") or row.get("currency") or "").strip().upper()
        currency = row_ccy or target_currency

        products.append(
            {
                "id": unesc(row.get("SKU", "")),
                "title": unesc(row.get("优化后标题", row.get("标题", ""))),
                "description": unesc(row.get("描述", "")),
                "link": unesc(row.get("链接", "")),
                "image_link": unesc(row.get("图片链接", "")),
                "additional_image_links": additional_links,
                "price": f"{price_amount:.2f}",
                "currency": currency,
                "sale_price": (
                    f"{float(row.get('sale_price', 0)):.2f}"
                    if float(row.get("sale_price", 0) or 0) > 0
                    else ""
                ),
                "availability": (
                    "in stock" if int(row.get("库存", 0) or 0) > 0 else "out of stock"
                ),
                "condition": "new",
                "brand": unesc(row.get("品牌", "")),
                "google_product_category": str(row.get("GPC代码", "")),
                "item_group_id": str(row.get("item_group_id", "")),
                "color": unesc(row.get("颜色", "")),
                "size": unesc(row.get("尺码", "")),
                "material": unesc(row.get("材质", "")),
                "gender": str(row.get("gender", "")),
                "age_group": str(row.get("age_group", "adult")),
                "shipping_weight": str(row.get("shipping_weight") or row.get("重量") or ""),
            }
        )

    return Template(META_XML_TEMPLATE, autoescape=True).render(
        products=products,
        shop_name=shop_name or "Store",
        site_link=site_link,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def save_meta_feed(
    rows: list[dict],
    output_path: Path,
    shop_name: str = "",
    site_link: str = "",
    country: str = "US",
) -> int:
    xml = generate_meta_feed(rows, shop_name, site_link, country)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding="utf-8")
    return xml.count("<item>")


class MetaPlatform:
    id = "meta"

    def export_feed(
        self,
        rows: list[dict],
        *,
        output_path: Path,
        country: str,
        shop_name: str = "",
        site_link: str = "",
        skip_out_of_stock: bool = False,
    ) -> int:
        return save_meta_feed(rows, output_path, shop_name, site_link, country)
