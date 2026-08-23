"""AdFeed AI — Feed XML 生成器 v4.0（GMC 合规强化）

- 静态模式：从 DataFrame 生成（兼容旧接口 + pipeline 内调用）
- 动态模式：从 PRODUCT_MEMORY_DB 实时查询 → 每个国家取对应语种标题
- Inventory 熔断：inventory==0 自动 out_of_stock
- 多国币种自动转换
- v4.0: 中文颜色/材质自动翻译英文 / title 追加颜色卖点 / size_system 自动填充
         shipping 默认值 / description 自动摘要 / additional_image_link 支持
"""

import pandas as pd
import os
import json
import re
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
      <g:id>{{ p.sku }}</g:id>
      <g:title>{{ p.optimized_title | e }}</g:title>
      <g:description>{{ p.description | e }}</g:description>
      <g:link>{{ p.link | e }}</g:link>
      <g:image_link>{{ p.image_url | e }}</g:image_link>
      {% if p.additional_image_links %}{% for img in p.additional_image_links %}<g:additional_image_link>{{ img | e }}</g:additional_image_link>{% endfor %}{% endif %}
      <g:price>{{ p.price }} {{ p.currency }}</g:price>
      {% if p.sale_price %}<g:sale_price>{{ p.sale_price }} {{ p.currency }}</g:sale_price>{% endif %}
      {% if p.sale_price_effective_date %}<g:sale_price_effective_date>{{ p.sale_price_effective_date }}</g:sale_price_effective_date>{% endif %}
      <g:availability>{{ p.availability }}</g:availability>
      <g:condition>new</g:condition>
      <g:identifier_exists>{{ p.identifier_exists }}</g:identifier_exists>
      {% if p.gtin %}<g:gtin>{{ p.gtin }}</g:gtin>{% endif %}
      {% if p.mpn %}<g:mpn>{{ p.mpn }}</g:mpn>{% endif %}
      {% if p.brand %}<g:brand>{{ p.brand | e }}</g:brand>{% endif %}
      {% if p.gpc_code %}<g:google_product_category>{{ p.gpc_code }}</g:google_product_category>{% endif %}
      {% if p.gpc_path %}<g:product_type>{{ p.gpc_path | e }}</g:product_type>{% endif %}
      {% if p.item_group_id %}<g:item_group_id>{{ p.item_group_id }}</g:item_group_id>{% endif %}
      {% if p.size %}<g:size>{{ p.size | e }}</g:size>{% endif %}
      {% if p.size_system %}<g:size_system>{{ p.size_system }}</g:size_system>{% endif %}
      {% if p.size_type %}<g:size_type>{{ p.size_type }}</g:size_type>{% endif %}
      {% if p.gender %}<g:gender>{{ p.gender }}</g:gender>{% endif %}
      {% if p.age_group %}<g:age_group>{{ p.age_group }}</g:age_group>{% endif %}
      {% if p.color %}<g:color>{{ p.color | e }}</g:color>{% endif %}
      {% if p.pattern %}<g:pattern>{{ p.pattern | e }}</g:pattern>{% endif %}
      {% if p.material %}<g:material>{{ p.material | e }}</g:material>{% endif %}
      {% if p.custom_label_0 %}<g:custom_label_0>{{ p.custom_label_0 | e }}</g:custom_label_0>{% endif %}
      {% if p.custom_label_1 %}<g:custom_label_1>{{ p.custom_label_1 | e }}</g:custom_label_1>{% endif %}
      {% if p.custom_label_2 %}<g:custom_label_2>{{ p.custom_label_2 | e }}</g:custom_label_2>{% endif %}
      {% if p.custom_label_3 %}<g:custom_label_3>{{ p.custom_label_3 | e }}</g:custom_label_3>{% endif %}
      {% if p.custom_label_4 %}<g:custom_label_4>{{ p.custom_label_4 | e }}</g:custom_label_4>{% endif %}
      {% if p.shipping %}<g:shipping><g:country>{{ p.shipping_country | e }}</g:country><g:service>{{ p.shipping_service | e }}</g:service><g:price>{{ p.shipping_price }} {{ p.currency }}</g:price></g:shipping>{% endif %}
      {% if p.shipping_weight %}<g:shipping_weight>{{ p.shipping_weight }}</g:shipping_weight>{% endif %}
      {% if p.min_handling_time > 0 %}<g:min_handling_time>{{ p.min_handling_time }}</g:min_handling_time>{% endif %}
      {% if p.max_handling_time > 0 %}<g:max_handling_time>{{ p.max_handling_time }}</g:max_handling_time>{% endif %}
      <g:adult>{{ p.adult }}</g:adult>
      {% if p.multipack > 0 %}<g:multipack>{{ p.multipack }}</g:multipack>{% endif %}
      {% if p.is_bundle == 'yes' %}<g:is_bundle>yes</g:is_bundle>{% endif %}
      {% if p.tax %}<g:tax><g:country>{{ p.shipping_country | e }}</g:country><g:rate>{{ p.tax }}</g:rate><g:tax_ship>no</g:tax_ship></g:tax>{% endif %}
      {% if p.energy_efficiency_class %}<g:energy_efficiency_class>{{ p.energy_efficiency_class }}</g:energy_efficiency_class>{% endif %}
      {% if p.unit_pricing_measure %}<g:unit_pricing_measure>{{ p.unit_pricing_measure }}</g:unit_pricing_measure>{% endif %}
      {% if p.unit_pricing_base_measure %}<g:unit_pricing_base_measure>{{ p.unit_pricing_base_measure }}</g:unit_pricing_base_measure>{% endif %}
    </item>
    {% endfor %}
  </channel>
</rss>
"""

_USD_EUR_RATE = float(os.getenv("ADFEED_USD_EUR", "0.92"))
EXCHANGE_RATES = {"USD": 1.0, "EUR": _USD_EUR_RATE}


def _deprecated_currency_for_country(country: str) -> str:
    from .market_pricing import expected_currency_for_country
    return expected_currency_for_country(country)


# Deprecated for feed submit: GMC requires landing-page currency match.
# Use market_pricing.resolve_market_price + row `_feed_currency` instead.

# ─────────────────────────────────────────────
# v4.0: 中文 → 英文颜色/材质翻译字典（GMC 合规）
# ─────────────────────────────────────────────

COLOR_ZH_EN = {
    "黑色": "Black", "白色": "White", "灰色": "Grey", "红色": "Red",
    "蓝色": "Blue", "绿色": "Green", "黄色": "Yellow", "粉色": "Pink",
    "紫色": "Purple", "橙色": "Orange", "棕色": "Brown", "卡其色": "Khaki",
    "米色": "Beige", "藏青": "Navy", "藏青色": "Navy", "驼色": "Camel",
    "酒红": "Burgundy", "酒红色": "Burgundy", "墨绿": "Dark Green",
    "浅蓝": "Light Blue", "深蓝": "Dark Blue", "浅灰": "Light Grey",
    "深灰": "Dark Grey", "银色": "Silver", "金色": "Gold", "玫瑰金": "Rose Gold",
    "透明": "Clear", "花色": "Multicolor", "迷彩": "Camouflage",
    "杏色": "Apricot", "裸色": "Nude", "军绿": "Army Green",
}

MATERIAL_ZH_EN = {
    "冰丝面料": "Ice Silk Fabric", "冰丝": "Ice Silk", "涤纶": "Polyester",
    "聚酯纤维": "Polyester", "氨纶": "Spandex", "棉": "Cotton",
    "纯棉": "100% Cotton", "真丝": "Silk", "桑蚕丝": "Mulberry Silk",
    "亚麻": "Linen", "棉麻": "Cotton Linen", "羊毛": "Wool",
    "羊绒": "Cashmere", "头层牛皮": "Genuine Leather", "牛皮": "Cowhide",
    "pu皮": "PU Leather", "人造革": "Faux Leather", "帆布": "Canvas",
    "尼龙": "Nylon", "316不锈钢": "316 Stainless Steel",
    "304不锈钢": "304 Stainless Steel", "不锈钢": "Stainless Steel",
    "硅胶": "Silicone", "塑料": "Plastic", "abs": "ABS",
    "亚克力": "Acrylic", "陶瓷": "Ceramic", "玻璃": "Glass",
    "竹": "Bamboo", "木": "Wood", "实木": "Solid Wood",
    "合金": "Alloy", "钛钢": "Titanium Steel", "925银": "925 Silver",
    "珍珠": "Pearl", "水晶": "Crystal", "蕾丝": "Lace",
    "雪纺": "Chiffon", "天鹅绒": "Velvet", "灯芯绒": "Corduroy",
    "牛仔": "Denim", "麂皮": "Suede", "仿麂皮": "Faux Suede",
}


def _translate_color(val: str) -> str:
    """中文颜色 → 英文，已是英文则原样返回"""
    if not val:
        return ""
    val_stripped = val.strip()
    # 已经是英文（无中文字符）
    if not any('\u4e00' <= c <= '\u9fff' for c in val_stripped):
        return val_stripped
    return COLOR_ZH_EN.get(val_stripped, val_stripped)


def _extract_dominant_color(color_val: str) -> str:
    """从图案描述中提取主色名（GMC 合规）

    取字符串中**最先出现**的颜色关键词作为主色。
    例: "Yellow background with black stripes" → "Yellow" (Yellow 在 Black 之前)
        "Pink base with black stripes" → "Pink"
        "White vertical stripe" → "White"
        "Black with white stripes" → "Black"
        "Style 1" → "" (无法推断，返回空让 GMC 忽略)
        "Apricot Flower" → "Apricot"
        "Navy Blue Flower" → "Navy Blue"
        "Dark Gray" → "Dark Gray"
    """
    if not color_val:
        return ""

    val = color_val.strip()

    # 已知标准颜色名（多词颜色在前，确保 "Navy Blue" 优先于 "Navy"/"Blue"）
    KNOWN_COLORS = [
        "Light Blue", "Dark Blue", "Sky Blue", "Navy Blue",
        "Dark Green", "Army Green", "Light Grey", "Dark Grey",
        "Light Gray", "Dark Gray",
        "Rose Gold", "Black", "White", "Red", "Blue", "Green",
        "Yellow", "Pink", "Purple", "Orange", "Brown", "Grey",
        "Gray", "Beige", "Khaki", "Navy", "Camel", "Burgundy",
        "Gold", "Silver", "Clear", "Multicolor", "Apricot",
        "Transparent",
    ]

    val_lower = val.lower()

    # 1. 如果本身就是标准颜色名，直接返回
    if val_lower in {c.lower() for c in KNOWN_COLORS}:
        return val.title() if val != val.title() else val

    # 2. 从图案描述中提取主色 — 按**在字符串中首次出现的位置**排序
    #    这样 "Yellow background with black stripes" 中 Yellow(pos=0) 先于 Black(pos=25)
    best_color = None
    best_pos = len(val) + 1
    for color_name in KNOWN_COLORS:
        pos = val_lower.find(color_name.lower())
        if pos >= 0 and pos < best_pos:
            best_pos = pos
            best_color = color_name
            if pos == 0:  # 不可能更早了
                break
    if best_color:
        return best_color

    # 3. "Style N" / "Pattern N" 等无法映射为颜色的值 → 返回空
    if val_lower.startswith(("style", "pattern", "款式", "花色")):
        return ""

    # 4. 无法识别 → 原样返回
    return val


def _format_material_value(val: str) -> str:
    """格式化材质值：确保百分比后有空格、首字母大写、+ 号两侧有空格

    例: "92%polyester+8%spandex" → "92% Polyester + 8% Spandex"
        "abs + silicone" → "ABS + Silicone"
    """
    if not val:
        return ""
    import re
    result = val.strip()
    # 1. 百分比后加空格: "92%polyester" → "92% Polyester"
    result = re.sub(r'(\d+)%\s*([a-zA-Z])', r'\1% \2', result)
    # 2. + 号两侧加空格: "Polyester+8%" → "Polyester + 8%"
    result = re.sub(r'\s*\+\s*', ' + ', result)
    # 3. 每个单词首字母大写（保留缩写如 ABS, PU）
    words = result.split()
    formatted = []
    for w in words:
        if w.isupper() and len(w) <= 4:  # ABS, PU, etc
            formatted.append(w)
        elif w == '+':
            formatted.append('+')
        else:
            formatted.append(w.capitalize())
    return ' '.join(formatted)


def _translate_material(val: str) -> str:
    """中文材质 → 英文，支持复合材质（如 92%聚酯纤维+8%氨纶）"""
    if not val:
        return ""
    val_stripped = val.strip()
    # 已经是英文（无中文字符）→ 仍需格式化
    if not any('\u4e00' <= c <= '\u9fff' for c in val_stripped):
        return _format_material_value(val_stripped)
    # 精确匹配
    if val_stripped in MATERIAL_ZH_EN:
        return MATERIAL_ZH_EN[val_stripped]
    # 复合材质模糊替换：将中文材质名逐个替换为英文
    # 例: "92%聚酯纤维+8%氨纶" → "92% Polyester + 8% Spandex"
    result = val_stripped
    # 按长度降序匹配（避免 "棉" 先于 "纯棉" 被替换）
    for zh, en in sorted(MATERIAL_ZH_EN.items(), key=lambda x: -len(x[0])):
        if zh in result:
            result = result.replace(zh, en)
    return _format_material_value(result)


from .config import DESCRIPTION_MAX_LENGTH

TITLE_MAX_CHARS = 150  # Google Shopping 标题上限（不再用 70 强制截断）
DESCRIPTION_MAX_CHARS = DESCRIPTION_MAX_LENGTH  # Google Shopping 描述上限 5000


def _soft_truncate(text: str, max_chars: int) -> str:
    """仅当超过平台硬上限时按词边界截断；否则原样返回。"""
    if not text or len(text) <= max_chars:
        return text or ""
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space].rstrip()
    return truncated.rstrip()


def _enhance_title(base_title: str, color: str, gender: str = "", brand: str = "",
                   material: str = "", size: str = "", gpc_path: str = "",
                   gpc_code: str = "", pattern: str = "") -> str:
    """Field contract: skeleton + brand? + this-row pattern/color/size once.

    Pattern is a variant differentiator for ALL product types (not dress-only).
    No material wall, no Plus Size injection, no Style N.
    """
    if not base_title:
        return ""
    from .title_guard import polish_feed_title

    en_color = _translate_color(color)

    # Skip handles / placeholder supplier brands in the title string
    brand_ok = bool(brand) and brand not in ("No Brand", "Unbranded", "Store", "")
    if brand_ok:
        b = brand.strip()
        if ".myshopify" in b.lower() or b.lower().endswith(".com"):
            brand_ok = False
        elif b.lower() in ("eprolo", "oem", "厂牌直供", "自主品牌"):
            brand_ok = False
        elif re.search(r"\d", b) and "-" in b and " " not in b:
            brand_ok = False  # qx2kd5-s7 style handle

    if brand_ok and brand.lower() not in base_title.lower():
        title_with_brand = f"{brand} {base_title}"
    else:
        title_with_brand = base_title

    full_title = polish_feed_title(
        title_with_brand,
        color=en_color or color,
        size=size,
        pattern=pattern,
        gpc_path=gpc_path,
        gpc_code=gpc_code,
    )
    full_title = _soft_truncate(full_title, TITLE_MAX_CHARS)
    full_title = re.sub(r"\s*\|\s*$", "", full_title)
    full_title = re.sub(r"\s*,\s*$", "", full_title)
    return full_title.rstrip()


def _auto_description(title: str, brand: str, material: str, color: str,
                      gender: str, product_type: str = "", size: str = "") -> str:
    """自动生成英文产品描述摘要（当 description 为空时使用）

    基于已有字段拼接 SEO 友好的描述文本，避免 GMC 数据质量警告。
    根据不同品类 + 颜色/尺码变体生成差异化描述，避免同品变体高度重复。
    """
    if not title:
        return ""
    en_material = _translate_material(material)
    en_color = _translate_color(color)

    # 第一句：品牌 + 标题（核心识别）
    if brand and brand not in ("No Brand", "Unbranded", ""):
        parts = [f"{brand} {title}."]
    else:
        parts = [f"{title}."]

    # 判断品类类型，生成差异化描述
    pt_lower = product_type.lower() if product_type else ""
    is_food = any(k in pt_lower for k in ["food", "beverage", "tea", "coffee", "snack", "supplement"])
    is_clothing = any(k in pt_lower for k in ["clothing", "shirt", "dress", "pant", "jacket"])
    is_shoes = any(k in pt_lower for k in ["shoes", "sneakers", "boots", "sandals"])
    is_electronics = any(k in pt_lower for k in ["electronics", "audio", "headphone", "earbud"])
    is_jewelry = any(k in pt_lower for k in ["jewelry", "earring", "necklace", "ring", "bracelet"])
    is_bags = any(k in pt_lower for k in ["bags", "backpack", "handbag", "wallet"])
    is_home = any(k in pt_lower for k in ["kitchen", "home", "household", "thermos", "cup"])

    # 第二句：材质/成分（按品类差异化）
    if en_material:
        if is_food:
            parts.append(f"Made with {en_material} for authentic flavor and quality.")
        elif "%" in en_material or "+" in en_material:
            parts.append(f"Crafted from premium {en_material} blend for durability and comfort.")
        elif any(m in en_material.lower() for m in ["cotton", "silk", "leather", "linen", "cashmere"]):
            parts.append(f"Made with high-quality {en_material} for a luxurious feel.")
        else:
            parts.append(f"Constructed from durable {en_material} for long-lasting use.")

    # 第三句：颜色/外观 — 基于颜色名 hash 选择不同句式（变体差异化核心）
    color_templates = [
        "Features a stylish {color} finish that pairs effortlessly with any wardrobe.",
        "Shown here in {color} — a versatile shade for every season.",
        "This {color} variant adds a fresh touch to your everyday look.",
        "Available in {color}, designed to complement your personal style.",
        "The {color} colorway offers a timeless aesthetic for any occasion.",
        "Dressed in {color} for a clean, modern appearance.",
    ]
    if en_color:
        if is_food:
            parts.append(f"Available in {en_color} packaging.")
        elif is_jewelry:
            parts.append(f"Beautifully finished in {en_color} for versatile styling.")
        else:
            # 用颜色名 hash 选择句式，确保同颜色始终得到相同句式
            idx = hash(en_color.lower()) % len(color_templates)
            parts.append(color_templates[idx].format(color=en_color))

    # 第四句：适用人群 + 场景（按品类）
    if is_food:
        parts.append("Perfect for daily enjoyment or as a thoughtful gift.")
    elif is_clothing:
        if gender == "male":
            parts.append("Designed for men's everyday comfort and style.")
        elif gender == "female":
            parts.append("Designed for women's everyday comfort and style.")
        else:
            parts.append("Suitable for all genders and occasions.")
    elif is_shoes:
        if gender == "male":
            parts.append("Built for men's all-day comfort and confident stride.")
        elif gender == "female":
            parts.append("Crafted for women's all-day comfort and elegant step.")
        else:
            parts.append("Engineered for all-day comfort and versatile wear.")
    elif is_electronics:
        parts.append("Engineered for reliable performance in daily use.")
    elif is_jewelry:
        parts.append("An elegant accessory for any occasion or outfit.")
    elif is_bags:
        parts.append("Spacious and organized for work, travel, or daily carry.")
    elif is_home:
        parts.append("A practical addition to your home or kitchen essentials.")
    else:
        if gender and gender != "unisex":
            gender_adj = "men's" if gender == "male" else "women's"
            parts.append(f"Designed for {gender_adj} everyday use.")
        else:
            parts.append("Suitable for all genders and occasions.")

    # 第五句：品类特性卖点 + 尺码信息（变体差异化）
    if is_clothing:
        if size:
            parts.append(f"Available in size {size} with a breathable, comfortable fit for all-day wear.")
        else:
            parts.append("Breathable fabric with comfortable fit for all-day wear.")
    elif is_shoes:
        if size:
            parts.append(f"Offered in size {size} with a supportive sole and cushioned insole.")
        else:
            parts.append("Supportive sole with cushioned insole for walking and casual use.")
    elif is_electronics:
        parts.append("Advanced technology with premium build quality.")
    elif is_bags:
        parts.append("Multiple compartments for efficient organization on the go.")
    elif is_home:
        parts.append("Thoughtful design with practical functionality.")
    elif is_jewelry:
        parts.append("Hypoallergenic materials safe for sensitive skin.")
    elif is_food:
        if size:
            parts.append(f"This {size} size is ideal for personal use or gifting.")
        else:
            parts.append("Carefully sourced and processed for maximum freshness.")
    elif product_type:
        parts.append("Quality construction for reliable everyday use.")

    return " ".join(parts)


# 国家 → size_system 映射
SIZE_SYSTEM_MAP = {
    "US": "US", "DE": "EU", "FR": "EU", "ES": "EU", "IT": "EU",
    "UK": "UK", "JP": "JP", "AU": "AU",
}

# 默认 shipping 配置（按国家）
DEFAULT_SHIPPING = {
    "US": {"country": "US", "service": "Standard Shipping", "price": 3.99},
    "DE": {"country": "DE", "service": "Standard Shipping", "price": 4.99},
    "FR": {"country": "FR", "service": "Standard Shipping", "price": 4.99},
    "ES": {"country": "ES", "service": "Standard Shipping", "price": 4.99},
    "IT": {"country": "IT", "service": "Standard Shipping", "price": 4.99},
}


def _convert_price(price_usd: float, country: str):
    """DEPRECATED — do not use for GMC/Meta/TikTok submit feeds.

    Kept only for legacy memory-path callers until migrated. Prefer
    ``market_pricing.resolve_market_price`` (no invented FX).
    """
    currency = _deprecated_currency_for_country(country)
    rate = EXCHANGE_RATES.get(currency, 1.0)
    return round(price_usd * rate, 2), currency


def _feed_price_and_currency(row, country: str) -> tuple[float, str]:
    """Use row amount as-is; currency from `_feed_currency` / `currency` / country map.

    Never multiplies by EXCHANGE_RATES.
    """
    price_str = str(row.get("价格", "0.00"))
    try:
        price_val = float(
            price_str.replace("USD", "").replace("EUR", "").replace("CNY", "").strip()
        )
    except (ValueError, AttributeError):
        price_val = 0.0

    currency = ""
    for key in ("_feed_currency", "currency", "币种"):
        raw = row.get(key, "")
        if raw is not None and str(raw).strip() and str(raw).strip().lower() != "nan":
            currency = str(raw).strip().upper()
            break
    if not currency:
        from .market_pricing import expected_currency_for_country
        currency = expected_currency_for_country(country)
    return round(price_val, 2), currency


def _price_label(price_usd: float) -> str:
    """根据价格返回区间标签（用于 custom_label_2）"""
    if price_usd <= 0:
        return ""
    if price_usd < 20:
        return "under-20"
    if price_usd < 50:
        return "under-50"
    if price_usd < 100:
        return "under-100"
    if price_usd < 200:
        return "under-200"
    return "over-200"


def _season_label(title: str, category: str = "") -> str:
    """根据标题/品类推断季节性标签（用于 custom_label_3）"""
    text = (title + " " + category).lower()
    seasons = {
        "spring": ["spring", "春", "easter"],
        "summer": ["summer", "夏", "beach", "swim", "sun"],
        "autumn": ["autumn", "fall", "秋", "halloween"],
        "winter": ["winter", "冬", "christmas", "xmas", "snow", "warm", "fleece"],
        "all-season": ["all season", "四季", "year round"],
    }
    for season, keywords in seasons.items():
        if any(kw in text for kw in keywords):
            return season
    return "all-season"


def _margin_label(price_usd: float, cost_cny: float = 0) -> str:
    """根据价格推断利润率标签（用于 custom_label_4）"""
    if price_usd <= 0:
        return ""
    # 粗略估算：如果只有售价，按价格区间推断
    if price_usd < 15:
        return "low-margin"
    if price_usd < 50:
        return "mid-margin"
    return "high-margin"


def _country_display(country: str) -> str:
    names = {"US": "United States", "DE": "Germany", "FR": "France", "ES": "Spain", "IT": "Italy"}
    return names.get(country.upper(), country.upper())


# ─────────────────────────────────────────────
# 静态模式：从 DataFrame 生成
# ─────────────────────────────────────────────

def generate(df: pd.DataFrame, country: str = "US", site_link: str = "https://adfeed.ai",
             skip_out_of_stock: bool = False) -> str:
    """从 DataFrame 生成 Feed XML

    Args:
        skip_out_of_stock: True 时跳过 inventory<=0 的变体，不输出到 Feed
    """
    products = []
    for _, row in df.iterrows():
        price, currency = _feed_price_and_currency(row, country)
        price_val = price
        raw_inv = row.get("库存", row.get("inventory", 0))
        inv = int(raw_inv) if raw_inv is not None and raw_inv != "" else 0

        # v4.2: 可选跳过断货商品（避免 GMC 商品诊断警告）
        if skip_out_of_stock and inv <= 0:
            continue

        # v3.1: link 字段强制使用绝对 URL（而非图片 URL 或相对路径）
        sku_val = str(row.get("SKU", "")).replace(" ", "-")  # ID 不允许含空格
        link_val = str(row.get("链接", ""))
        if not link_val or "image" in link_val.lower() or (link_val.startswith("http") and (".jpg" in link_val or ".png" in link_val or ".webp" in link_val)):
            link_val = f"{site_link}/products/{sku_val}"
        elif link_val.startswith("/"):
            # 相对路径 → 绝对 URL
            link_val = f"{site_link}{link_val}"

        # v3.0: custom_label 智能填充
        custom_label_0 = str(row.get("custom_label_0", ""))
        custom_label_1 = str(row.get("custom_label_1", ""))
        custom_label_2 = str(row.get("custom_label_2", "")) or _price_label(price_val)
        custom_label_3 = str(row.get("custom_label_3", "")) or _season_label(
            str(row.get("优化后标题", row.get("标题", ""))),
            str(row.get("GPC路径", ""))
        )
        custom_label_4 = str(row.get("custom_label_4", "")) or _margin_label(price_val)

        # v3.0: 默认值强制填充
        condition = str(row.get("condition", "new")).strip() or "new"
        availability = str(row.get("availability", "")).strip()
        if not availability:
            availability = "out_of_stock" if inv <= 0 else "in_stock"
        identifier_exists = str(row.get("identifier_exists", "no")).strip() or "no"

        # v4.0: 中文颜色/材质自动翻译英文（GMC 合规）
        # P0: Style/脏后缀 → 基础色（结合描述 Color: 列表）
        from .attribute_normalizer import resolve_gmc_color
        raw_color = str(row.get("颜色", "")) if pd.notna(row.get("颜色")) else ""
        raw_material = str(row.get("材质", "")) if pd.notna(row.get("材质")) else ""
        ctx_desc = str(row.get("描述", "") or "")
        ctx_title = str(row.get("标题", "") or row.get("优化后标题", "") or "")
        en_color = resolve_gmc_color(raw_color, description=ctx_desc, title=ctx_title)
        if not en_color:
            en_color = _extract_dominant_color(_translate_color(raw_color))
        en_material = _translate_material(raw_material)

        # v4.0: title 增强 — 追加品牌 + 颜色 + 材质卖点 + 品类纪律
        base_title = str(row.get("优化后标题", row.get("标题", "")))
        brand_val = str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else ""
        raw_size = str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else ""
        gpc_path_val = str(row.get("GPC路径", "") or "")
        gpc_code_val = str(row.get("GPC代码", "") or "")
        enhanced_title = _enhance_title(
            base_title, en_color or raw_color, str(row.get("gender", "")), brand_val,
            raw_material, size=raw_size, gpc_path=gpc_path_val, gpc_code=gpc_code_val,
            pattern=str(row.get("pattern") or row.get("custom_label_0") or ""),
        )
        from .attribute_normalizer import normalize_gender
        gender_now = str(row.get("gender", "") or "").strip()
        gender_seed = "" if gender_now.lower() in ("", "nan", "unisex") else gender_now
        gender_now = normalize_gender(
            gender_seed, f"{enhanced_title} {base_title}"
        ) or gender_now or "unisex"

        # description：优先保留 Shopify/库内完整文案，格式化属性粘连；硬上限 5000
        from .desc_formatter import format_product_description
        raw_desc = str(row.get("描述", "") or "")
        if not raw_desc.strip() or len(raw_desc.strip()) < 10:
            # 其次用 AI snippet
            snip = str(row.get("description_snippet", "") or "")
            if snip.strip() and len(snip.strip()) >= 10:
                raw_desc = snip
            else:
                raw_desc = _auto_description(
                    base_title, brand_val,
                    raw_material, raw_color,
                    str(row.get("gender", "")),
                    str(row.get("GPC路径", "")),
                    size=str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else "",
                )
        raw_desc = format_product_description(raw_desc.strip(), max_chars=DESCRIPTION_MAX_CHARS)
        if not raw_desc:
            raw_desc = _auto_description(
                base_title, brand_val,
                raw_material, raw_color,
                str(row.get("gender", "")),
                str(row.get("GPC路径", "")),
                size=str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else "",
            )
            raw_desc = format_product_description(raw_desc, max_chars=DESCRIPTION_MAX_CHARS)
        # soft truncate already applied inside formatter; keep as safety
        raw_desc = _soft_truncate(raw_desc.strip(), DESCRIPTION_MAX_CHARS)

        # v4.0: size_system 自动填充（智能检测尺码体系）
        raw_size_system = str(row.get("size_system", ""))
        raw_size = str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else ""
        if not raw_size_system:
            # 智能检测：纯数字尺码（36/37/38/39/40/41/42/43/44/45）通常是欧码
            if raw_size.isdigit() and 30 <= int(raw_size) <= 50:
                raw_size_system = "EU"
            else:
                raw_size_system = SIZE_SYSTEM_MAP.get(country.upper(), "")

        # v4.0: shipping 默认值
        raw_shipping = row.get("shipping", False)
        raw_shipping_country = str(row.get("shipping_country", ""))
        raw_shipping_service = str(row.get("shipping_service", ""))
        raw_shipping_price = str(row.get("shipping_price", "0"))
        if not raw_shipping and not raw_shipping_country:
            # 自动启用默认 shipping
            default_ship = DEFAULT_SHIPPING.get(country.upper())
            if default_ship:
                raw_shipping = True
                raw_shipping_country = default_ship["country"]
                raw_shipping_service = default_ship["service"]
                raw_shipping_price = f"{default_ship['price']:.2f}"

        # v4.1: shipping_weight 默认值（按品类推断，避免 GMC 缺失警告）
        raw_shipping_weight = str(row.get("shipping_weight", "")).strip()
        if not raw_shipping_weight or raw_shipping_weight == "nan":
            gpc_path_val = str(row.get("GPC路径", "")).lower()
            if any(k in gpc_path_val for k in ["coat", "jacket", "outerwear"]):
                raw_shipping_weight = "800.0 g"
            elif any(k in gpc_path_val for k in ["jean", "pant", "dress"]):
                raw_shipping_weight = "400.0 g"
            elif any(k in gpc_path_val for k in ["shirt", "top", "blouse", "vest"]):
                raw_shipping_weight = "250.0 g"
            elif any(k in gpc_path_val for k in ["sock", "underwear"]):
                raw_shipping_weight = "100.0 g"
            elif any(k in gpc_path_val for k in ["jumpsuit", "romper"]):
                raw_shipping_weight = "350.0 g"
            else:
                raw_shipping_weight = "300.0 g"  # 通用默认值

        # v4.0: additional_image_link 解析
        additional_images_raw = str(row.get("附加图片", ""))
        additional_links = []
        if additional_images_raw and additional_images_raw != "nan":
            try:
                img_list = json.loads(additional_images_raw)
                if isinstance(img_list, list):
                    additional_links = [img for img in img_list if img]
            except (json.JSONDecodeError, TypeError):
                additional_links = [u.strip() for u in additional_images_raw.split(",") if u.strip()]

        # v4.1: 去重 — additional_image_link 不能包含主图（GMC 明确禁止）
        main_image_url = str(row.get("图片链接", ""))
        if main_image_url:
            additional_links = [img for img in additional_links if img != main_image_url]
        # 去重 — 移除重复的附加图片 URL
        seen_imgs = set()
        deduped_links = []
        for img in additional_links:
            if img not in seen_imgs:
                seen_imgs.add(img)
                deduped_links.append(img)
        additional_links = deduped_links

        product_data = {
            "sku": sku_val,
            "optimized_title": enhanced_title,
            "description": raw_desc,
            "link": link_val,
            "image_url": str(row.get("图片链接", "")),
            "additional_image_links": additional_links,
            "price": f"{price:.2f}",
            "currency": currency,
            "sale_price": "",
            "sale_price_effective_date": "",
            "availability": availability,
            "identifier_exists": identifier_exists,
            "gtin": str(row.get("gtin", "")),
            "mpn": str(row.get("mpn", "") or "").strip(),
            "gpc_code": str(row.get("GPC代码", "")),
            "gpc_path": str(row.get("GPC路径", "")),
            "brand": str(row.get("品牌", "")) if pd.notna(row.get("品牌")) else "",
            "item_group_id": str(row.get("item_group_id", "")),
            "color": en_color,
            "pattern": str(row.get("pattern") or row.get("custom_label_0") or ""),
            "material": en_material,
            "size": str(row.get("尺码", "")) if pd.notna(row.get("尺码")) else "",
            "size_system": raw_size_system,
            "size_type": str(row.get("size_type", "")),
            "gender": gender_now,
            "age_group": str(row.get("age_group", "adult")),
            "custom_label_0": custom_label_0,
            "custom_label_1": custom_label_1,
            "custom_label_2": custom_label_2,
            "custom_label_3": custom_label_3,
            "custom_label_4": custom_label_4,
            "shipping": bool(raw_shipping),
            "shipping_country": raw_shipping_country,
            "shipping_service": raw_shipping_service or "Standard Shipping",
            "shipping_price": raw_shipping_price,
            "shipping_weight": raw_shipping_weight,
            "min_handling_time": int(row.get("min_handling_time", 0) or 0),
            "max_handling_time": int(row.get("max_handling_time", 0) or 0),
            "adult": str(row.get("adult", "no")),
            "multipack": int(row.get("multipack", 0) or 0),
            "is_bundle": str(row.get("is_bundle", "no")),
            "tax": str(row.get("tax", "")),
            "energy_efficiency_class": str(row.get("energy_efficiency_class", "")),
            "unit_pricing_measure": str(row.get("unit_pricing_measure", "")),
            "unit_pricing_base_measure": str(row.get("unit_pricing_base_measure", "")),
        }
        products.append(product_data)

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
    skip_out_of_stock: bool = False,
):
    """从 PRODUCT_MEMORY_DB 动态生成指定国家的 Feed XML

    Args:
        skip_out_of_stock: True 时跳过 inventory<=0 的变体
    """
    from .product_memory import get_all_active

    all_products = get_all_active(target_country=target_country)

    products = []
    in_stock_count = 0
    out_of_stock_count = 0

    for p in all_products:
        inventory = int(p.get("inventory", 0))
        # Prefer explicit feed currency; do not FX-convert for submit
        from .market_pricing import expected_currency_for_country
        price = round(float(p.get("price_usd", 0) or 0), 2)
        currency = str(p.get("currency") or p.get("_feed_currency") or "").strip().upper()
        if not currency:
            currency = expected_currency_for_country(target_country)

        availability = "out_of_stock" if inventory <= 0 else "in_stock"

        if inventory <= 0:
            out_of_stock_count += 1
            if skip_out_of_stock:
                continue
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
        # v4.1: 去重 — additional_image_link 不能包含主图
        main_img = _safe_str(p.get("image_url", ""), "")
        if main_img:
            additional_links = [img for img in additional_links if img != main_img]
        # 去重 — 移除重复的附加图片 URL
        seen_imgs = set()
        deduped_links = []
        for img in additional_links:
            if img not in seen_imgs:
                seen_imgs.add(img)
                deduped_links.append(img)
        additional_links = deduped_links

        # v4.1: 颜色主色提取 + 标题截断
        raw_color = _safe_str(p.get("color", ""), "")
        en_color = _extract_dominant_color(_translate_color(raw_color))
        raw_material = _safe_str(p.get("material", ""), "")
        en_material = _translate_material(raw_material)
        base_title = _safe_str(optimized_title, "Product")
        enhanced_title = _enhance_title(
            base_title, en_color or raw_color,
            _safe_str(p.get("gender", ""), ""),
            _safe_str(p.get("brand", ""), ""),
            raw_material,
            size=_safe_str(p.get("size", ""), ""),
            gpc_path=_safe_str(p.get("gpc_path", ""), ""),
            gpc_code=_safe_str(p.get("gpc_code", ""), ""),
            pattern=_safe_str(p.get("pattern", ""), "") or _safe_str(p.get("custom_label_0", ""), ""),
        )

        # v4.1: shipping_weight 默认值
        sw = _safe_str(p.get("shipping_weight", ""), "").strip()
        if not sw:
            gpc_path_val = _safe_str(p.get("gpc_path", ""), "").lower()
            if any(k in gpc_path_val for k in ["coat", "jacket", "outerwear"]):
                sw = "800.0 g"
            elif any(k in gpc_path_val for k in ["jean", "pant", "dress"]):
                sw = "400.0 g"
            elif any(k in gpc_path_val for k in ["shirt", "top", "blouse", "vest"]):
                sw = "250.0 g"
            elif any(k in gpc_path_val for k in ["sock", "underwear"]):
                sw = "100.0 g"
            elif any(k in gpc_path_val for k in ["jumpsuit", "romper"]):
                sw = "350.0 g"
            else:
                sw = "300.0 g"

        products.append({
            "sku": p.get("product_id", ""),
            "optimized_title": enhanced_title,
            "description": _safe_str(description, ""),
            "link": f"{site_link}/products/{p.get('product_id', '')}",
            "image_url": main_img,
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
            "color": en_color,
            "material": en_material,
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
            "shipping_weight": sw,
            "min_handling_time": int(p.get("min_handling_time", 0) or 0),
            "max_handling_time": int(p.get("max_handling_time", 0) or 0),
            "adult": p.get("adult", "no"),
            "multipack": int(p.get("multipack", 0) or 0),
            "is_bundle": p.get("is_bundle", "no"),
            "tax": p.get("tax", ""),
            "energy_efficiency_class": p.get("energy_efficiency_class", ""),
            "unit_pricing_measure": p.get("unit_pricing_measure", ""),
            "unit_pricing_base_measure": p.get("unit_pricing_base_measure", ""),
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
