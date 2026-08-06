"""AdFeed AI — 属性标准化与翻译引擎 v1.0

将 1688/速卖通/手工表的非标属性自动清洗为 GMC 标准值。
覆盖：颜色翻译、尺码标准化、材质翻译、Gender/Age Group 推断。
支持 5 个目标语种（US/DE/FR/ES/IT）。
"""

import re
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# 颜色翻译字典 — 中文 → 多语种标准色名
# ═══════════════════════════════════════════════════════════════

COLOR_MAP: dict[str, dict[str, str]] = {
    # 基础色
    "黑色": {"US": "Black", "DE": "Schwarz", "FR": "Noir", "ES": "Negro", "IT": "Nero"},
    "白色": {"US": "White", "DE": "Weiß", "FR": "Blanc", "ES": "Blanco", "IT": "Bianco"},
    "红色": {"US": "Red", "DE": "Rot", "FR": "Rouge", "ES": "Rojo", "IT": "Rosso"},
    "蓝色": {"US": "Blue", "DE": "Blau", "FR": "Bleu", "ES": "Azul", "IT": "Blu"},
    "绿色": {"US": "Green", "DE": "Grün", "FR": "Vert", "ES": "Verde", "IT": "Verde"},
    "黄色": {"US": "Yellow", "DE": "Gelb", "FR": "Jaune", "ES": "Amarillo", "IT": "Giallo"},
    "粉色": {"US": "Pink", "DE": "Rosa", "FR": "Rose", "ES": "Rosa", "IT": "Rosa"},
    "紫色": {"US": "Purple", "DE": "Lila", "FR": "Violet", "ES": "Morado", "IT": "Viola"},
    "橙色": {"US": "Orange", "DE": "Orange", "FR": "Orange", "ES": "Naranja", "IT": "Arancione"},
    "灰色": {"US": "Gray", "DE": "Grau", "FR": "Gris", "ES": "Gris", "IT": "Grigio"},
    "棕色": {"US": "Brown", "DE": "Braun", "FR": "Marron", "ES": "Marrón", "IT": "Marrone"},
    "米色": {"US": "Beige", "DE": "Beige", "FR": "Beige", "ES": "Beige", "IT": "Beige"},
    "卡其色": {"US": "Khaki", "DE": "Khaki", "FR": "Kaki", "ES": "Caqui", "IT": "Khaki"},
    " navy": {"US": "Navy", "DE": "Marineblau", "FR": "Bleu Marine", "ES": "Azul Marino", "IT": "Blu Navy"},
    "藏青色": {"US": "Navy", "DE": "Marineblau", "FR": "Bleu Marine", "ES": "Azul Marino", "IT": "Blu Navy"},
    "驼色": {"US": "Camel", "DE": "Kamel", "FR": "Camel", "ES": "Camel", "IT": "Cammello"},
    "酒红色": {"US": "Burgundy", "DE": "Burgund", "FR": "Bordeaux", "ES": "Burdeos", "IT": "Bordeaux"},
    "墨绿色": {"US": "Dark Green", "DE": "Dunkelgrün", "FR": "Vert Foncé", "ES": "Verde Oscuro", "IT": "Verde Scuro"},
    "浅蓝色": {"US": "Light Blue", "DE": "Hellblau", "FR": "Bleu Clair", "ES": "Azul Claro", "IT": "Blu Chiaro"},
    "深蓝色": {"US": "Dark Blue", "DE": "Dunkelblau", "FR": "Bleu Foncé", "ES": "Azul Oscuro", "IT": "Blu Scuro"},
    "天蓝色": {"US": "Sky Blue", "DE": "Himmelblau", "FR": "Bleu Ciel", "ES": "Celeste", "IT": "Celeste"},
    "军绿色": {"US": "Army Green", "DE": "Armeegrün", "FR": "Vert Militaire", "ES": "Verde Militar", "IT": "Verde Militare"},
    "杏色": {"US": "Apricot", "DE": "Aprikose", "FR": "Abricot", "ES": "Albaricoque", "IT": "Albicocca"},
    "裸色": {"US": "Nude", "DE": "Nude", "FR": "Nude", "ES": "Nude", "IT": "Nude"},
    "透明": {"US": "Clear", "DE": "Transparent", "FR": "Transparent", "ES": "Transparente", "IT": "Trasparente"},
    "金色": {"US": "Gold", "DE": "Gold", "FR": "Doré", "ES": "Dorado", "IT": "Oro"},
    "银色": {"US": "Silver", "DE": "Silber", "FR": "Argenté", "ES": "Plateado", "IT": "Argento"},
    "玫瑰金": {"US": "Rose Gold", "DE": "Roségold", "FR": "Or Rose", "ES": "Oro Rosa", "IT": "Oro Rosa"},
    "原木色": {"US": "Natural Wood", "DE": "Naturholz", "FR": "Bois Naturel", "ES": "Madera Natural", "IT": "Legno Naturale"},
    "多彩": {"US": "Multicolor", "DE": "Mehrfarbig", "FR": "Multicolore", "ES": "Multicolor", "IT": "Multicolore"},
}

# 英文颜色名直通（已经是英文的不用翻译）
_ENGLISH_COLORS = {
    "black", "white", "red", "blue", "green", "yellow", "pink", "purple",
    "orange", "gray", "grey", "brown", "beige", "khaki", "navy", "camel",
    "burgundy", "gold", "silver", "clear", "transparent", "multicolor",
    "rose gold", "light blue", "dark blue", "sky blue", "army green",
}

# ═══════════════════════════════════════════════════════════════
# 尺码标准化 — 中文 → GMC 标准尺码
# ═══════════════════════════════════════════════════════════════

SIZE_MAP: dict[str, str] = {
    # 中文尺码
    "均码": "One Size", "自由码": "One Size", "通用": "One Size", "通用款": "One Size",
    "XS": "XS", "S": "S", "M": "M", "L": "L", "XL": "XL",
    "XXL": "XXL", "2XL": "XXL", "3XL": "XXXL", "4XL": "XXXXL", "5XL": "XXXXL",
    "大码": "XL", "加大": "XL", "加大码": "XL", "特大": "XXL", "特大码": "XXL",
    "小码": "S", "小": "S", "中码": "M", "中": "M", "大": "L",
    # 数字尺码（鞋类）
    "35": "35", "36": "36", "37": "37", "38": "38", "39": "39",
    "40": "40", "41": "41", "42": "42", "43": "43", "44": "44",
    "45": "45", "46": "46",
    # 童装尺码
    "80": "80", "90": "90", "100": "100", "110": "110", "120": "120",
    "130": "130", "140": "140", "150": "150", "160": "160",
}

# ═══════════════════════════════════════════════════════════════
# 材质翻译字典 — 中文 → 多语种标准材质名
# ═══════════════════════════════════════════════════════════════

MATERIAL_MAP: dict[str, dict[str, str]] = {
    "棉": {"US": "Cotton", "DE": "Baumwolle", "FR": "Coton", "ES": "Algodón", "IT": "Cotone"},
    "纯棉": {"US": "100% Cotton", "DE": "Reine Baumwolle", "FR": "100% Coton", "ES": "100% Algodón", "IT": "100% Cotone"},
    "涤纶": {"US": "Polyester", "DE": "Polyester", "FR": "Polyester", "ES": "Poliéster", "IT": "Poliestere"},
    "聚酯纤维": {"US": "Polyester", "DE": "Polyester", "FR": "Polyester", "ES": "Poliéster", "IT": "Poliestere"},
    "丝绸": {"US": "Silk", "DE": "Seide", "FR": "Soie", "ES": "Seda", "IT": "Seta"},
    "真丝": {"US": "Real Silk", "DE": "Echte Seide", "FR": "Soie Véritable", "ES": "Seda Natural", "IT": "Seta Naturale"},
    "雪纺": {"US": "Chiffon", "DE": "Chiffon", "FR": "Mousseline", "ES": "Gasa", "IT": "Chiffon"},
    "蕾丝": {"US": "Lace", "DE": "Spitze", "FR": "Dentelle", "ES": "Encaje", "IT": "Pizzo"},
    "牛仔": {"US": "Denim", "DE": "Denim", "FR": "Denim", "ES": "Denim", "IT": "Denim"},
    "亚麻": {"US": "Linen", "DE": "Leinen", "FR": "Lin", "ES": "Lino", "IT": "Lino"},
    "羊毛": {"US": "Wool", "DE": "Wolle", "FR": "Laine", "ES": "Lana", "IT": "Lana"},
    "羊绒": {"US": "Cashmere", "DE": "Kaschmir", "FR": "Cachemire", "ES": "Cachemira", "IT": "Cashmere"},
    "尼龙": {"US": "Nylon", "DE": "Nylon", "FR": "Nylon", "ES": "Nailon", "IT": "Nylon"},
    "氨纶": {"US": "Spandex", "DE": "Elasthan", "FR": "Élasthanne", "ES": "Elastano", "IT": "Elastan"},
    "皮革": {"US": "Leather", "DE": "Leder", "FR": "Cuir", "ES": "Cuero", "IT": "Pelle"},
    "PU皮": {"US": "PU Leather", "DE": "PU-Leder", "FR": "Simili Cuir", "ES": "Cuero PU", "IT": "Pelle PU"},
    "人造革": {"US": "Faux Leather", "DE": "Kunstleder", "FR": "Simili Cuir", "ES": "Piel Sintética", "IT": "Pelle Sintetica"},
    "塑料": {"US": "Plastic", "DE": "Kunststoff", "FR": "Plastique", "ES": "Plástico", "IT": "Plastica"},
    "金属": {"US": "Metal", "DE": "Metall", "FR": "Métal", "ES": "Metal", "IT": "Metallo"},
    "不锈钢": {"US": "Stainless Steel", "DE": "Edelstahl", "FR": "Acier Inoxydable", "ES": "Acero Inoxidable", "IT": "Acciaio Inossidabile"},
    "铝合金": {"US": "Aluminum Alloy", "DE": "Aluminiumlegierung", "FR": "Alliage d'Aluminium", "ES": "Aleación de Aluminio", "IT": "Lega di Alluminio"},
    "亚克力": {"US": "Acrylic", "DE": "Acryl", "FR": "Acrylique", "ES": "Acrílico", "IT": "Acrilico"},
    "硅胶": {"US": "Silicone", "DE": "Silikon", "FR": "Silicone", "ES": "Silicona", "IT": "Silicone"},
    "橡胶": {"US": "Rubber", "DE": "Gummi", "FR": "Caoutchouc", "ES": "Caucho", "IT": "Gomma"},
    "玻璃": {"US": "Glass", "DE": "Glas", "FR": "Verre", "ES": "Vidrio", "IT": "Vetro"},
    "陶瓷": {"US": "Ceramic", "DE": "Keramik", "FR": "Céramique", "ES": "Cerámica", "IT": "Ceramica"},
    "木质": {"US": "Wood", "DE": "Holz", "FR": "Bois", "ES": "Madera", "IT": "Legno"},
    "天然木材": {"US": "Natural Wood", "DE": "Naturholz", "FR": "Bois Naturel", "ES": "Madera Natural", "IT": "Legno Naturale"},
    "竹子": {"US": "Bamboo", "DE": "Bambus", "FR": "Bambou", "ES": "Bambú", "IT": "Bambù"},
    "记忆棉": {"US": "Memory Foam", "DE": "Memory-Schaum", "FR": "Mousse à Mémoire", "ES": "Viscoelástica", "IT": "Memory Foam"},
    "无纺布": {"US": "Non-Woven", "DE": "Vlies", "FR": "Non-Tissé", "ES": "No Tejido", "IT": "Non Tessuto"},
    "牛津布": {"US": "Oxford Fabric", "DE": "Oxford-Gewebe", "FR": "Tissu Oxford", "ES": "Tela Oxford", "IT": "Tessuto Oxford"},
    "帆布": {"US": "Canvas", "DE": "Leinwand", "FR": "Toile", "ES": "Lona", "IT": "Tela"},
    "网布": {"US": "Mesh", "DE": "Netzgewebe", "FR": "Filet", "ES": "Malla", "IT": "Rete"},
    "碳纤维": {"US": "Carbon Fiber", "DE": "Kohlefaser", "FR": "Fibre de Carbone", "ES": "Fibra de Carbono", "IT": "Fibra di Carbonio"},
    "钛钢": {"US": "Titanium Steel", "DE": "Titanstahl", "FR": "Acier Titane", "ES": "Acero Titanio", "IT": "Acciaio Titanio"},
    "925银": {"US": "925 Sterling Silver", "DE": "925 Sterlingsilber", "FR": "Argent 925", "ES": "Plata 925", "IT": "Argento 925"},
    "合金": {"US": "Alloy", "DE": "Legierung", "FR": "Alliage", "ES": "Aleación", "IT": "Lega"},
    "ABS": {"US": "ABS", "DE": "ABS", "FR": "ABS", "ES": "ABS", "IT": "ABS"},
    "PC": {"US": "PC", "DE": "PC", "FR": "PC", "ES": "PC", "IT": "PC"},
    "TPE": {"US": "TPE", "DE": "TPE", "FR": "TPE", "ES": "TPE", "IT": "TPE"},
    "TPU": {"US": "TPU", "DE": "TPU", "FR": "TPU", "ES": "TPU", "IT": "TPU"},
}

# ═══════════════════════════════════════════════════════════════
# 组合材质拆分（如 "金属+亚克力" → "Metal & Acrylic"）
# ═══════════════════════════════════════════════════════════════

_COMPOSITE_SEPARATORS = re.compile(r'[+＋/、,，]')


def normalize_color(cn_color: str, country: str = "US") -> str:
    """中文颜色 → 目标语种标准色名

    如果已经是英文则直接返回（首字母大写）。
    """
    if not cn_color:
        return ""

    color = cn_color.strip()
    country = country.upper()

    # 已经是英文
    if color.lower() in _ENGLISH_COLORS:
        return color.title()

    # 精确匹配
    if color in COLOR_MAP:
        return COLOR_MAP[color].get(country, color)

    # 模糊匹配（处理 "深蓝色"、"浅粉色" 等）
    for cn_key, translations in COLOR_MAP.items():
        if cn_key in color or color in cn_key:
            return translations.get(country, color)

    # 包含中文但无法翻译 → 返回空（让 AI 标题中的颜色词替代）
    if re.search(r'[\u4e00-\u9fff]', color):
        return ""

    return color


def normalize_size(cn_size: str) -> str:
    """中文尺码 → GMC 标准尺码"""
    if not cn_size:
        return ""

    size = cn_size.strip()

    # 精确匹配
    if size in SIZE_MAP:
        return SIZE_MAP[size]

    # 模糊匹配（处理 "XL码", "加大XL" 等）
    for cn_key, std_size in SIZE_MAP.items():
        if cn_key in size or size in cn_key:
            return std_size

    # 已经是标准尺码格式
    if re.match(r'^(XS|S|M|L|XL|XXL|XXXL|XXXXL|One Size|\d{2,3})$', size, re.IGNORECASE):
        return size

    return size


def normalize_material(cn_material: str, country: str = "US") -> str:
    """中文材质 → 目标语种标准材质名

    支持组合材质拆分（如 "金属+亚克力" → "Metal & Acrylic"）。
    """
    if not cn_material:
        return ""

    material = cn_material.strip()
    country = country.upper()

    # 检查是否是组合材质（用 + / 、 分隔）
    if _COMPOSITE_SEPARATORS.search(material):
        parts = _COMPOSITE_SEPARATORS.split(material)
        translated_parts = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if part in MATERIAL_MAP:
                translated_parts.append(MATERIAL_MAP[part].get(country, part))
            elif part.lower() in {v.lower() for v in ["cotton", "polyester", "silk", "denim", "leather", "metal", "plastic", "glass", "wood", "rubber"]}:
                translated_parts.append(part)
            else:
                translated_parts.append(part)
        connector = " & " if country == "US" else " & "
        return connector.join(translated_parts)

    # 精确匹配
    if material in MATERIAL_MAP:
        return MATERIAL_MAP[material].get(country, material)

    # 模糊匹配
    for cn_key, translations in MATERIAL_MAP.items():
        if cn_key in material or material in cn_key:
            return translations.get(country, material)

    # 包含中文但无法翻译 → 返回空
    if re.search(r'[\u4e00-\u9fff]', material):
        return ""

    return material


def normalize_gender(raw_gender: str, title: str = "") -> str:
    """标准化 Gender 为 GMC 标准值: male / female / unisex"""
    if not raw_gender and not title:
        return "unisex"

    text = (raw_gender + " " + title).lower()
    # 使用整词匹配（避免 "men" 匹配 "women" 的子串 bug）
    words = set(re.findall(r'[a-z\u4e00-\u9fff]+', text))

    female_signals = {"women", "womens", "woman", "female", "女", "女士", "女装",
                      "damen", "femme", "mujer", "donna", "girls", "少女"}
    male_signals = {"men", "mens", "man", "male", "男", "男士", "男装",
                    "herren", "homme", "hombre", "uomo", "boys", "少年"}

    has_female = bool(words & female_signals) or any(s in text for s in female_signals if len(s) > 4)
    has_male = bool(words & male_signals)
    # 排除冲突：如果同时有 female 和 male 信号，以明确的为准
    if has_female and has_male:
        # "women" 包含 "men" 子串，但 "women" 本身是女性信号
        if "women" in words or "womens" in words or "woman" in words:
            has_male = False
        elif "men" in words and "women" not in words:
            has_female = False

    if has_female and not has_male:
        return "female"
    elif has_male and not has_female:
        return "male"
    return "unisex"


def normalize_age_group(raw_age: str, title: str = "", category: str = "") -> str:
    """标准化 Age Group 为 GMC 标准值: adult / kids / toddler / infant"""
    if not raw_age and not title and not category:
        return "adult"

    text = (raw_age + " " + title + " " + category).lower()

    infant_signals = {"infant", "newborn", "baby", "新生儿", "婴儿", "0-1"}
    toddler_signals = {"toddler", "幼儿", "学步", "1-3", "kids baby"}
    kids_signals = {"kids", "children", "child", "儿童", "kid", "boy", "girl",
                    "学生", "teen", "青少年", "3-12"}

    if any(s in text for s in infant_signals):
        return "infant"
    if any(s in text for s in toddler_signals):
        return "toddler"
    if any(s in text for s in kids_signals):
        return "kids"
    return "adult"


def normalize_all_attributes(row: dict, country: str = "US") -> dict:
    """一次性标准化所有属性，返回 GMC-ready 的字段字典

    Args:
        row: 包含原始属性的字典，键名可以是中文或英文
        country: 目标市场代码

    Returns:
        {
            "color": "Black",
            "material": "Cotton",
            "size": "L",
            "gender": "female",
            "age_group": "adult",
            "size_system": "US",
        }
    """
    # 提取原始值（兼容中英文键名）
    raw_color = (row.get("颜色", "") or row.get("color", "") or "").strip()
    raw_size = (row.get("尺码", "") or row.get("size", "") or "").strip()
    raw_material = (row.get("材质", "") or row.get("material", "") or "").strip()
    raw_gender = (row.get("gender", "") or "").strip()
    raw_age = (row.get("age_group", "") or "").strip()
    title = (row.get("标题", "") or row.get("title", "") or "").strip()
    category = (row.get("分类", "") or row.get("category", "") or "").strip()

    return {
        "color": normalize_color(raw_color, country),
        "material": normalize_material(raw_material, country),
        "size": normalize_size(raw_size),
        "gender": normalize_gender(raw_gender, title),
        "age_group": normalize_age_group(raw_age, title, category),
        "size_system": "US" if country == "US" else ("EU" if country in ("DE", "FR", "ES", "IT") else ""),
    }
