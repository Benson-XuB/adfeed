"""AdFeed AI — 合规违禁词正则拦截防火墙

四层规则引擎，检查并清洗商品标题，输出违规标注和建议。
"""

import re

# ============================================
# Layer 1: 极限词规则（全局 — 自动删除）
# ============================================
SUPERLATIVE_RULES = [
    # 英文极限词
    (r'\bbest\b', '', '极限词'),
    (r'\bno\.?\s*1\b', '', '极限词'),
    (r'\b#\s*1\b', '', '极限词'),
    (r'\btop\s*1\b', '', '极限词'),
    (r'\bnumber\s*one\b', '', '极限词'),
    (r'\bworld[\s-]?class\b', 'High Quality', '极限词'),
    (r'\bguaranteed\b', '', '极限词'),
    (r'\bperfect\b', 'Great', '极限词'),
    (r'\bamazing\b', 'Great', '极限词'),
    (r'\bincredible\b', 'Great', '极限词'),
    (r'\bunbeatable\b', 'Competitive', '极限词'),
    (r'\blockdown\s*price', 'affordable', '极限词'),
    (r'\bcheapest\b', 'affordable', '极限词'),
    (r'\b100%\s*(natural|pure|organic|safe|effective|guarantee)', r'\1', '虚假100%宣称'),
    # 中文极限词
    (r'业界第一', '', '极限词'),
    (r'全球首发', '', '极限词'),
    (r'独家', '', '极限词'),
    (r'全网最低', '', '极限词'),
    (r'第一品牌', '', '极限词'),
    (r'顶级', '高端', '极限词'),
    (r'国家级', '', '极限词'),
    (r'世界级', '', '极限词'),
    (r'全网独家', '', '极限词'),
    (r'极致', '优质', '极限词'),
    (r'万能', '多功能', '极限词'),
    (r'最佳', '', '极限词'),
    (r'史上最', '', '极限词'),
    (r'销量第一', '', '极限词'),
    (r'排名第一', '', '极限词'),
    (r'榜首', '', '极限词'),
    (r'全网第一', '', '极限词'),
    (r'第一', '', '极限词'),
]

# ============================================
# Layer 2: 侵权品牌词（全局 — 标记警告）
# ============================================
TRADEMARK_KEYWORDS = [
    "Nike", "Adidas", "Gucci", "Louis Vuitton", "LV", "Chanel",
    "Apple", "Samsung", "Sony", "Rolex", "Prada", "Hermès", "Hermes",
    "Dior", "Burberry", "Supreme", "Yeezy", "Balenciaga",
    "Cartier", "Tiffany", "Versace", "Moncler", "Canada Goose",
    "Bose", "JBL", "Beats", "Under Armour", "Reebok",
    "North Face", "Patagonia", "Arc'teryx", "Fendi", "Givenchy",
]

# ============================================
# Layer 3: 敏感描述词（全局 — 标记警告）
# ============================================
SENSITIVE_RULES = [
    # 医疗宣称
    (r'\b(cure|cures|cured|curing)\b', '禁止医疗宣称 (cure)'),
    (r'\b(heal|heals|healing|healed)\b', '禁止医疗宣称 (heal)'),
    (r'\b(treat|treats|treatment|therapy|therapeutic)\b', '禁止医疗宣称'),
    (r'\b(antibacterial|antimicrobial|杀菌|抑菌|消毒|抗菌)\b', '禁止抗菌宣称'),
    # 减肥 / 虚假功效
    (r'\b(weight\s*loss|lose\s*weight|fat\s*burning|slimming|减肥|燃脂|瘦身)\b', '禁止减肥功效宣称'),
    (r'\b(anti[\s-]?aging|抗衰老|抗皱)\b', '禁止未经证实的抗衰宣称'),
    # 成人内容
    (r'\b(sex|sexy|erotic|成人|情趣)\b', '成人内容风险'),
]

# ============================================
# Layer 3b: 欧盟特有规则
# ============================================
EU_SENSITIVE_RULES = [
    (r'\b(eco[\s-]?friendly|environmentally\s*friendly)\b', '欧盟: 禁止无依据环保宣称'),
    (r'\b(biodegradable|compostable)\b', '欧盟: 需提供可降解认证'),
    (r'\b(organic|bio)\b', '欧盟: 有机宣称需认证编号'),
]


def check_and_clean(text: str, country: str = "US") -> dict:
    """合规检查并自动清洗文本

    Args:
        text: 待检查的标题文本
        country: 目标国家代码 (US/DE/FR/ES/IT)

    Returns:
        {
            "clean_text": "清洗后的文本",
            "violations": [{"rule": "...", "word": "...", "action": "removed|replaced|warning", "suggestion": "..."}],
            "status": "pass" | "warning",
            "count": 违规数
        }
    """
    cleaned = text
    violations = []

    # Layer 1: 极限词 — 删除/替换
    for pattern, replacement, category in SUPERLATIVE_RULES:
        matches = re.finditer(pattern, cleaned, re.IGNORECASE if pattern.startswith(r'\b') else 0)
        for m in matches:
            word = m.group()
            violations.append({
                "layer": "superlative",
                "rule": category,
                "word": word,
                "action": "removed" if not replacement else f"replaced → '{replacement}'",
                "suggestion": replacement if replacement else "已删除",
            })
            cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE if pattern.startswith(r'\b') else 0)

    # Layer 2: 侵权品牌词 — 标记警告
    for brand in TRADEMARK_KEYWORDS:
        pattern = re.compile(r'\b' + re.escape(brand) + r'\b', re.IGNORECASE)
        if pattern.search(cleaned):
            violations.append({
                "layer": "trademark",
                "rule": "侵权品牌词",
                "word": brand,
                "action": "warning",
                "suggestion": f"请确认是否获得 {brand} 品牌授权，否则建议移除",
            })

    # Layer 3: 敏感描述 — 标记警告
    for pattern, desc in SENSITIVE_RULES:
        if re.search(pattern, cleaned, re.IGNORECASE):
            violations.append({
                "layer": "sensitive",
                "rule": desc,
                "word": re.search(pattern, cleaned, re.IGNORECASE).group(),
                "action": "warning",
                "suggestion": f"建议修改: {desc}",
            })

    # Layer 3b: 欧盟特有
    if country.upper() in ("DE", "FR", "ES", "IT", "NL"):
        for pattern, desc in EU_SENSITIVE_RULES:
            if re.search(pattern, cleaned, re.IGNORECASE):
                violations.append({
                    "layer": "sensitive_eu",
                    "rule": desc,
                    "word": re.search(pattern, cleaned, re.IGNORECASE).group(),
                    "action": "warning",
                    "suggestion": f"建议修改或提供认证: {desc}",
                })

    # 清理多余空格
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    status = "warning" if violations else "pass"

    return {
        "clean_text": cleaned,
        "violations": violations,
        "status": status,
        "count": len(violations),
    }


def check_size_merge(variants: list[dict], threshold: int = 5) -> dict:
    """尺码合并降噪：当变体超过阈值时触发合并

    Args:
        variants: [{"sku": "...", "size": "S"}, {"sku": "...", "size": "M"}, ...]
        threshold: 触发合并的最小变体数

    Returns:
        {
            "was_merged": True/False,
            "merged_groups": ["S-M", "L-XL"],
            "original_count": 8,
            "merged_count": 3,
        }
    """
    original_count = len(variants)

    if original_count < threshold:
        return {
            "was_merged": False,
            "merged_groups": [],
            "original_count": original_count,
            "merged_count": original_count,
        }

    # 标准尺码顺序
    size_order = ["XS", "S", "M", "L", "XL", "XXL", "2XL", "3XL",
                  "4", "6", "8", "10", "12", "14", "16", "18"]

    sizes = [v.get("size", "").strip().upper() for v in variants]

    # 尝试标准尺码链合并
    merged = []
    i = 0
    while i < len(size_order) - 1:
        current = size_order[i]
        next_sz = size_order[i + 1]
        if current in sizes and next_sz in sizes:
            merged.append(f"{current}-{next_sz}")
            i += 1  # 跳过下一个（已合并）
        elif current in sizes:
            merged.append(current)
        i += 1

    # 若标准尺码链合并不够，回退到简单方国案
    if len(merged) >= original_count / 2:
        return {
            "was_merged": True,
            "merged_groups": merged[:4],
            "original_count": original_count,
            "merged_count": len(merged[:4]),
        }

    merged_count = max(3, original_count // 2)
    return {
        "was_merged": True,
        "merged_groups": [f"Variant-{i+1}" for i in range(merged_count)],
        "original_count": original_count,
        "merged_count": merged_count,
    }


# ═══════════════════════════════════════════════════════════════
# L2 产品属性推断 — gender / age_group / item_group_id
# ═══════════════════════════════════════════════════════════════

def infer_product_attributes(
    category_key: str = "",
    gpc_path: str = "",
    original_title: str = "",
    color: str = "",
    material: str = "",
    search_prefix: str = "",
    size: str = "",
) -> dict:
    """从品类和 GPC 路径推断 gender / age_group / item_group_id。

    GMC 强制要求：
    - Apparel 品类必须填 gender + age_group
    - 同款不同尺码/颜色必须共享 item_group_id

    Returns:
        {"gender": "male|female|unisex", "age_group": "adult|kids|...",
         "item_group_id": "<md5 hash>"}
    """
    # 1. gender 推断 — word-boundary check 防止 "women" 中 "men" 误匹配
    gender = "unisex"
    title_words = set(original_title.lower().split())
    search_words = set(search_prefix.lower().split())

    # 去标点干扰: "Women's" → "womens"
    title_words = set(w.strip(",.!?;:'\"()") for w in title_words)
    search_words = set(w.strip(",.!?;:'\"()") for w in search_words)
    all_words = title_words | search_words

    female_words = {"women", "womens", "woman", "female", "damen", "femme", "mujer",
                    "donna", "dress", "dresses", "skirt", "skirts", "bra", "lingerie",
                    "maternity", "nursing", "girls", "ladies"}
    male_words = {"men", "mens", "man", "male", "herren", "homme", "hombre",
                  "uomo", "boys", "gentlemen", "suit", "suits", "blazer", "blazers",
                  "tie", "ties", "bowtie"}

    has_female = bool(all_words & female_words)
    has_male = bool(all_words & male_words)

    if has_female and not has_male:
        gender = "female"
    elif has_male and not has_female:
        gender = "male"
    elif has_female and has_male:
        gender = "unisex"

    # 2. age_group 推断
    age_group = "adult"
    title_lower = original_title.lower()
    if category_key in ("toys_kids_baby",):
        age_group = "kids"
    if any(k in gpc_path.lower() for k in ["baby", "infant", "toddler", "newborn"]):
        age_group = "infant"
    if any(k in title_lower for k in ["baby", "infant", "toddler", "newborn", "kids", "child"]):
        age_group = "kids"

    # 3. item_group_id — 同款不同 size/color 共用（hash 剔除已知尺码词）
    import hashlib, re
    stem_title = re.sub(r'\b(XS|S|M|L|XL|XXL|2XL|3XL|4XL|5XL|\d+)\b', '', original_title, flags=re.IGNORECASE)
    stem_title = re.sub(r'\s+', ' ', stem_title).strip()
    stem = f"{stem_title[:50]}|{color}|{material}"
    item_group_id = hashlib.md5(stem.lower().strip().encode()).hexdigest()[:12]

    return {
        "gender": gender,
        "age_group": age_group,
        "item_group_id": item_group_id,
    }


# ═══════════════════════════════════════════════════════════════
# L3 图片水印检测 — URL 关键词扫描
# ═══════════════════════════════════════════════════════════════

_WATERMARK_SIGNALS = [
    "1688", "alibaba", "taobao", "淘宝", "天猫", "tmall",
    "水印", "watermark",
    "详情", "实拍", "厂家直销", "批发", "一件代发",
    "联系客服", "支持定制", "免费拿样",
    "wechat", "微信", "qq", "whatsapp",
    "taobao.com", "tmall.com", "1688.com",
    "新品推荐", "爆款", "热卖",
]


def scan_image_watermarks(image_urls: list[str]) -> dict:
    """扫描图片 URL 中的水印/中文电商关键词。

    Args:
        image_urls: 图片链接列表

    Returns:
        {
            "clean": True/False,
            "flagged_urls": ["url1", "url2"],
            "signals_found": ["1688", "水印"],
            "suggestion": "建议替换或裁剪以下图片: ..."
        }
    """
    if not image_urls:
        return {"clean": True, "flagged_urls": [], "signals_found": [], "suggestion": ""}

    flagged = []
    signals_found = set()

    for url in image_urls:
        url_lower = url.lower()
        for signal in _WATERMARK_SIGNALS:
            if signal.lower() in url_lower:
                flagged.append(url)
                signals_found.add(signal)

    if flagged:
        return {
            "clean": False,
            "flagged_urls": flagged,
            "signals_found": sorted(signals_found),
            "suggestion": f"检测到 {len(flagged)} 张图片含中文电商水印关键词，GMC 可能拒审。建议替换或裁剪图片。",
        }

    return {"clean": True, "flagged_urls": [], "signals_found": [], "suggestion": ""}

# ═══════════════════════════════════════════════════════════════
# L4 欧盟能效等级推断（电子产品强制）
# ═══════════════════════════════════════════════════════════════

_ENERGY_EFFICIENCY_KEYWORDS = {
    "refrigerator": "F", "fridge": "F", "freezer": "F",
    "washing machine": "D", "washer": "D", "dishwasher": "E",
    "dryer": "B", "tumble dryer": "B",
    "oven": "A", "microwave": "A",
    "air conditioner": "A++", "ac unit": "A++",
    "tv": "G", "television": "G", "monitor": "F",
    "lamp": "A", "light bulb": "A", "led bulb": "A",
    "vacuum cleaner": "A",
}


def infer_energy_efficiency_class(gpc_path: str = "", original_title: str = "") -> str:
    """从 GPC 路径/标题推断欧盟能效等级。

    仅对 Electronics 和 Home & Garden 下的特定电器品类生效。
    无匹配返回空字符串（非强制品类不填此字段）。
    """
    search_text = (gpc_path + " " + original_title).lower()
    for keyword, rating in _ENERGY_EFFICIENCY_KEYWORDS.items():
        if keyword in search_text:
            return rating
    return ""
