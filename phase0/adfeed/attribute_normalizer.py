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
    "XXL": "XXL", "XXXL": "XXXL", "XXXXL": "XXXXL", "XXXXXL": "XXXXXL",
    "2XL": "2XL", "3XL": "3XL", "4XL": "4XL", "5XL": "5XL",
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


# GMC 标准色（多词在前，便于从描述中抽取）
# Colorful is NOT a hue — it belongs in _MULTICOLOR_PHRASES.
_GMC_KNOWN_COLORS = [
    "Light Blue", "Dark Blue", "Sky Blue", "Navy Blue",
    "Dark Green", "Army Green", "Light Grey", "Dark Grey",
    "Light Gray", "Dark Gray", "Rose Gold",
    "Black", "White", "Red", "Blue", "Green", "Yellow", "Pink",
    "Purple", "Orange", "Brown", "Grey", "Gray", "Beige", "Khaki",
    "Navy", "Camel", "Burgundy", "Gold", "Silver", "Clear",
    "Multicolor", "Apricot", "Transparent", "Nude",
]

# Phrases meaning "unnameable many colors" → Multicolor (not GMC hues).
_MULTICOLOR_PHRASES = (
    "mixed color", "mixed colours", "mixed colors",
    "multi color", "multi colour", "multicolor",
    "colorful", "colourful",
    "assorted",
)
_MULTICOLOR_CJK = ("花色", "多彩", "多色", "混色")
_GMC_HUE_COLORS = tuple(
    c for c in _GMC_KNOWN_COLORS if c.lower() != "multicolor"
)

_STYLE_LABEL_RE = re.compile(
    r"^(style|pattern|color|colour|款式|花色|颜色)\s*[-_]?\s*\d+$",
    re.I,
)
_COLOR_LINE_RE = re.compile(
    r"(?:^|\n|<[^>]+>)\s*color\s*[:：]\s*([^\n<#]+)",
    re.I,
)


def _strip_color_noise(raw: str) -> str:
    """去掉营销括号/方括号等噪音，保留色名。"""
    if not raw:
        return ""
    s = raw.strip()
    s = re.sub(r"\[.*?\]", " ", s)
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[*【】]", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" ,;/|-")
    return s


def _named_hue(cleaned: str) -> str:
    """Extract a real GMC hue (never Multicolor / Colorful)."""
    if not cleaned:
        return ""
    low = cleaned.lower()
    for name in _GMC_HUE_COLORS:
        if low == name.lower():
            return name
    mapped = normalize_color(cleaned, "US")
    if mapped:
        for name in _GMC_HUE_COLORS:
            if mapped.lower() == name.lower():
                return name
    best, best_pos = None, len(cleaned) + 1
    for name in _GMC_HUE_COLORS:
        pos = low.find(name.lower())
        if pos >= 0 and pos < best_pos:
            best, best_pos = name, pos
            if pos == 0:
                break
    return best or ""


def _is_multicolor_synonym(cleaned: str) -> bool:
    """True when the token is a many-colors phrase, not a hue name."""
    if not cleaned:
        return False
    if any(k in cleaned for k in _MULTICOLOR_CJK):
        return True
    norm = re.sub(r"[-_]+", " ", cleaned.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    for phrase in _MULTICOLOR_PHRASES:
        if re.search(rf"(?<![a-z]){re.escape(phrase)}(?![a-z])", norm):
            return True
    return False


def _canonical_color_token(token: str) -> str:
    """单段色名 → GMC 标准写法；无法识别则空。

    Named hue wins; only if none, many-color synonyms → Multicolor.
    """
    if not token:
        return ""
    cleaned = _strip_color_noise(token)
    if not cleaned:
        return ""
    hue = _named_hue(cleaned)
    if hue:
        return hue
    if _is_multicolor_synonym(cleaned):
        return "Multicolor"
    return ""


def parse_listed_colors(description: str) -> list[str]:
    """从商品描述 `Color: Black, Khaki` / `Color: brown` 解析色列表。"""
    if not description:
        return []
    # 去 HTML 标签便于匹配
    text = re.sub(r"<[^>]+>", "\n", description)
    text = text.replace("&nbsp;", " ")
    m = _COLOR_LINE_RE.search(text)
    if not m:
        return []
    raw_list = m.group(1)
    parts = re.split(r"[,，/;|]+", raw_list)
    out = []
    seen = set()
    for part in parts:
        c = _canonical_color_token(part.strip())
        if c and c.lower() not in seen:
            seen.add(c.lower())
            out.append(c)
    return out


def _is_style_label(raw: str) -> bool:
    if not raw:
        return False
    return bool(_STYLE_LABEL_RE.match(_strip_color_noise(raw) or raw.strip()))


def _style_index(raw: str) -> int:
    """Style 1 → 0, Style 2 → 1；无法解析 → -1。"""
    m = re.search(r"(\d+)", raw or "")
    if not m:
        return -1
    return max(0, int(m.group(1)) - 1)


# Opaque non-color / non-size axes (any catalog — not product-specific)
_OPAQUE_AXIS_RE = re.compile(
    r"^(?:style|design|type|model|version|edition|款式|型号|款)\s*[-_]?\s*([a-z0-9]+)$",
    re.I,
)


def opaque_style_axis_key(raw: str) -> str:
    """Stable slug for opaque style/design options (Style 1, Design A, 款式2…).

    High-quality Shopping: these are often different garments sharing one Shopify
    product. Caller should split item_group_id by this key — never dump into
    title or pretend they are print patterns.
    """
    cleaned = (_strip_color_noise(raw) or (raw or "")).strip()
    if not cleaned:
        return ""
    if _is_style_label(cleaned):
        m = re.search(r"([a-z0-9]+)\s*$", cleaned, re.I)
        token = (m.group(1) if m else "x").lower()
        return f"style-{token}"
    m = _OPAQUE_AXIS_RE.match(cleaned)
    if m:
        head = re.match(r"^[a-z\u4e00-\u9fff]+", cleaned, re.I)
        prefix = (head.group(0) if head else "style").lower()
        # normalize Chinese prefixes
        prefix = {
            "款式": "style", "型号": "model", "款": "style",
        }.get(prefix, prefix)
        return f"{prefix}-{m.group(1).lower()}"
    return ""


_COLOR_STOPWORDS = {
    "with", "and", "the", "a", "an", "base", "background", "color", "colour",
}


def _title_case_color_words(text: str) -> str:
    parts = []
    for w in text.split():
        if w.isupper() and len(w) <= 3:
            parts.append(w)
        else:
            parts.append(w[:1].upper() + w[1:].lower() if w else w)
    return " ".join(parts)


def extract_pattern_from_color_raw(raw: str, hue: str = "") -> str:
    """Non-hue tokens from option text → GMC pattern (not merged into color)."""
    cleaned = _strip_color_noise(raw or "")
    if not cleaned:
        return ""
    if _is_style_label(cleaned):
        return ""  # Style N is not a searchable pattern (field contract)
    rest = cleaned
    if hue:
        for part in sorted(hue.split(), key=len, reverse=True):
            rest = re.sub(rf"\b{re.escape(part)}\b", " ", rest, flags=re.I)
    tokens = []
    for tok in re.split(r"[^A-Za-z0-9]+", rest):
        if not tok or tok.lower() in _COLOR_STOPWORDS:
            continue
        if _is_multicolor_synonym(tok):
            continue
        if _canonical_color_token(tok):
            continue
        tokens.append(tok)
    if not tokens:
        return ""
    low = " ".join(tokens).lower()
    if "flower" in low or "floral" in low:
        return "Floral"
    if "stripe" in low or "striped" in low:
        if "vertical" in low:
            return "Vertical Stripe"
        if "curved" in low:
            return "Curved Stripe"
        return "Stripe"
    if "dot" in low or "polka" in low:
        return "Polka Dot"
    # Style-only already returned above; bare style words are not patterns
    if _is_style_label(cleaned) or re.match(r"^style\s*\d+$", cleaned, re.I):
        return ""
    return _title_case_color_words(" ".join(tokens))[:40]


def resolve_gmc_color(
    raw_color: str,
    *,
    description: str = "",
    title: str = "",
) -> str:
    """GMC hue only — never merge Style/print into color (field contract)."""
    color, _pattern = resolve_gmc_color_and_pattern(
        raw_color, description=description, title=title,
    )
    return color


def resolve_gmc_color_and_pattern(
    raw_color: str,
    *,
    description: str = "",
    title: str = "",
) -> tuple[str, str]:
    """Return (gmc_color, pattern). Pattern empty when none."""
    raw = (raw_color or "").strip()
    listed = parse_listed_colors(description)
    context_blob = f"{title or ''} {re.sub(r'<[^>]+>', ' ', description or '')}"[:500]

    def _from_context() -> str:
        if listed:
            return listed[0]
        return _canonical_color_token(context_blob) or "Multicolor"

    hue = ""
    if raw and not _is_style_label(raw):
        hit = _canonical_color_token(raw)
        if hit:
            hue = hit
        else:
            hue = _from_context()
    elif listed:
        idx = _style_index(raw) if raw else 0
        if idx < 0:
            idx = 0
        if len(listed) == 1:
            hue = listed[0]
        else:
            hue = listed[min(idx, len(listed) - 1)]
    else:
        hue = _from_context()

    pattern = extract_pattern_from_color_raw(raw, hue=hue if hue != "Multicolor" else "")
    return hue, pattern


_LETTER_SIZE_RE = re.compile(
    r"^(XXXXXL|XXXXL|XXXL|XXL|5XL|4XL|3XL|2XL|XL|XS|S|M|L)(?:\s*码)?$",
    re.I,
)


def normalize_size(cn_size: str) -> str:
    """中文/字母尺码 → GMC 尺码。禁止把 XXXL 收成 L、把 4XL 与 5XL 收成同一个值。"""
    if not cn_size:
        return ""

    size = cn_size.strip()
    letter = _LETTER_SIZE_RE.match(size)
    if letter:
        return letter.group(1).upper()

    if size in SIZE_MAP:
        return SIZE_MAP[size]
    for key, std in SIZE_MAP.items():
        if key.lower() == size.lower():
            return std

    # 仅用长度≥2 的中文别名做包含匹配，避免 "L" in "XL"
    for cn_key, std_size in SIZE_MAP.items():
        if not re.search(r"[\u4e00-\u9fff]", cn_key):
            continue
        if len(cn_key) >= 2 and cn_key in size:
            return std_size

    if re.match(r"^(One Size)$", size, re.I):
        return "One Size"
    if re.match(r"^\d{2,3}$", size):
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
