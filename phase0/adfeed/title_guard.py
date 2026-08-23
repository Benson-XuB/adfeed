"""Shopping title guards: category-aware claims + variant differentiation."""
from __future__ import annotations

import re


# 允许 Tummy Control / Slimming 的品类信号
_TUMMY_OK = (
    "dress", "dresses", "jumpsuit", "romper", "pant", "pants", "jean", "jeans",
    "skirt", "legging", "shapewear", "bodysuit",
)

# 外套/袜/配饰：禁用塑身话术
_TUMMY_BAN_PATH = (
    "outerwear", "jacket", "coat", "vest", "sock", "hosiery", "underwear",
    "belt", "accessory", "shoe", "bag",
)

# 非裙装时降权的场景词（可整段删除）
_SCENE_PHRASES = [
    r"summer\s+friday(?:\s*&\s*brunch)?",
    r"weekend\s+brunch",
    r"for\s+summer\s+friday(?:\s*&\s*brunch)?",
    r"for\s+weekend\s+brunch(?:\s*&\s*[^,|]+)?",
    r"for\s+brunch(?:\s*&\s*[^,|]+)?",
    r"&\s*brunch",
    r"brunch\s*&\s*",
    r"\bbrunch\b",
    r"summer\s+friday",
    # Weak padding scenes — not shopper-searchable differentiators
    r"for\s+everyday\s+casual",
    r"for\s+everyday(?:\s+wear)?",
    r"for\s+streetwear\s+casual",
    r"for\s+streetwear",
]

# Trailing filler after apparel type (often injected by old sanitize / assets)
_TRAILING_CASUAL_RE = re.compile(
    r"\b(Jacket|Coat|Vest|Socks|Sock|Top|Blouse|Shirt|Dress|Jeans|Pants|Jumpsuit|Romper|Skirt|Shorts)"
    r"\s+Casual\b",
    re.I,
)

_TUMMY_PHRASES = [
    r"tummy\s*control(?:\s*fit)?",
    r"slimming\s+effect",
    r"\bslimming\b",
]

_CATEGORY_NOUNS = (
    "Jumpsuit", "Romper", "Dress", "Jacket", "Coat", "Jeans", "Pants",
    "Vest", "Socks", "Sock", "Blouse", "Shirt", "Top", "Skirt", "Shorts",
)


def _path_blob(gpc_path: str, gpc_code: str = "") -> str:
    return f"{gpc_path or ''} {gpc_code or ''}".lower()


def allows_tummy_control(gpc_path: str = "", gpc_code: str = "") -> bool:
    blob = _path_blob(gpc_path, gpc_code)
    if any(k in blob for k in _TUMMY_BAN_PATH):
        return False
    if any(k in blob for k in _TUMMY_OK):
        return True
    # 未知服饰默认不允许（宁缺勿滥）
    return False


def _cleanup_spaces(text: str) -> str:
    text = re.sub(r"\s*([,|/])\s*", r"\1 ", text)
    text = re.sub(r"\s{2,}", " ", text)
    text = re.sub(r"\s+,", ",", text)
    text = re.sub(r",\s*,+", ",", text)
    text = re.sub(r"\s*\|\s*\|+", " | ", text)
    # 场景词切除后的残片：for & Office / for , / & Office
    text = re.sub(r"\bfor\s*&\s*", "for ", text, flags=re.I)
    text = re.sub(r"\bfor\s*,\s*", "for ", text, flags=re.I)
    text = re.sub(r"\s+&\s+([A-Z])", r" \1", text)
    text = re.sub(r"^(?:for|and|&|,|\|)\s+", "", text, flags=re.I)
    text = re.sub(r"\s+(?:for|and|&|,|\|)$", "", text, flags=re.I)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip(" ,|/-")


def _fix_for_remnants(text: str) -> str:
    """把误用的 for + 规格词改成逗号列举（for Regular fit / for Long Sleeve / for S-XXL）。"""
    if not text:
        return ""
    out = text
    # for Regular/Slim/Loose fit → , Regular fit
    out = re.sub(
        r"\s+for\s+((?:regular|slim|loose|relaxed|oversized|skinny|straight)\s+fit)\b",
        r", \1",
        out,
        flags=re.I,
    )
    # for Long/Short Sleeve / Sleeveless / V-Neck …
    out = re.sub(
        r"\s+for\s+((?:long|short)\s+sleeves?|sleeveless|v-?neck|crew\s+neck|round\s+neck|halter(?:\s+neck)?)\b",
        r", \1",
        out,
        flags=re.I,
    )
    # for Sizes S-XXL
    out = re.sub(r"\s+for\s+(sizes?\s+[A-Za-z0-9–\-~/]+)", r", \1", out, flags=re.I)
    # for S-XXL / for S–5XL（尺码范围被当成场合）
    out = re.sub(
        r"\s+for\s+((?:[0-9]?X{0,4}S|[0-9]?X{0,4}M|[0-9]?X{0,4}L|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)"
        r"(?:\s*[–\-~/]\s*(?:[0-9]?X{0,4}S|[0-9]?X{0,4}M|[0-9]?X{0,4}L|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL))?)\b",
        r", Sizes \1",
        out,
        flags=re.I,
    )
    # 裸留的 "for ," / 双逗号
    out = re.sub(r"\s+for\s*,", ",", out, flags=re.I)
    out = re.sub(r",\s*,+", ",", out)
    return out


_FABRIC_WALL_RE = re.compile(
    r"\b(?:"
    r"polyester|spandex|elastane|nylon(?:\s*[-/]\s*spandex)?(?:\s+blend)?|"
    r"nylon-spandex(?:\s+blend)?|pu\b|pvc\b"
    r")\b",
    re.I,
)
_SEARCHABLE_MATERIAL_RE = re.compile(
    r"\b(?:denim|leather|silk|cashmere|merino(?:\s+wool)?|cotton|linen|wool)\b",
    re.I,
)
_FIT_DUMP_RE = re.compile(
    r"\b(?:"
    r"(?:regular|slim|loose|relaxed|oversized|skinny|straight|fitted)\s+fit|"
    r"fit\s+type|slim\s+fit"
    r")\b",
    re.I,
)
_CLOSURE_DUMP_RE = re.compile(
    r"(?:"
    r"\b(?:pullover|zipper|button|hook)\s+closure\b|"
    r"\bzipper\s+fly\b|"
    r"\bclosure\s+type\b|"
    r"\bclosure\b"
    r")",
    re.I,
)
_DOC_SYMBOL_RE = re.compile(r"[•\|]+")
_COATS_JACKETS_RE = re.compile(r"\bCoats?\s+Jackets?\b", re.I)
_MARKETING_FLUFF_RE = re.compile(
    r"\b(?:"
    r"anti-?slip|non-?slip|antibacterial|anti-?bacterial|"
    r"sweat-?absorbent|breathable|sweat-?wicking|moisture-?wicking|"
    r"odor-?resistant|quick-?dry|ultra-?thin|thin"
    r")\b",
    re.I,
)
_INLINE_SIZE_GARBAGE_RE = re.compile(
    r",?\s*\bX\s+Size\s+(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)\b",
    re.I,
)
_SIZE_LABEL_RE = re.compile(
    r",?\s*\bSize\s+(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL|One\s+Size)\b",
    re.I,
)
_TRAILING_BARE_SIZE_RE = re.compile(
    r",?\s*\b(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)\s*$",
    re.I,
)


def _strip_dangling_color_dot(title: str) -> str:
    """Drop leaked ' Black.' after apparel type (LLM material/color debris)."""
    out = (title or "").strip()
    if not out:
        return ""
    for noun in sorted(_CATEGORY_NOUNS, key=len, reverse=True):
        pat = re.compile(
            rf"(\b{re.escape(noun)}s?\b)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\.?\s*$",
            re.I,
        )
        m = pat.search(out)
        if m:
            return _cleanup_spaces(out[: m.end(1)])
    return out


def _strip_post_type_marketing_spam(title: str) -> str:
    """Drop non-searchable feature spam after the last apparel type noun."""
    if not title:
        return ""
    out = title
    best_end = -1
    for noun in sorted(_CATEGORY_NOUNS, key=len, reverse=True):
        last = None
        for mobj in re.finditer(rf"\b{re.escape(noun)}s?\b", out, re.I):
            last = mobj
        if last and last.end() > best_end:
            best_end = last.end()
    if best_end < 0:
        return _cleanup_spaces(_MARKETING_FLUFF_RE.sub(" ", out))
    head, tail = out[:best_end], out[best_end:]
    tail = _MARKETING_FLUFF_RE.sub(" ", tail)
    return _cleanup_spaces(head + tail)


def strip_inline_size_mentions(title: str) -> str:
    """Remove stale Size labels before appending this row's authoritative size."""
    out = strip_size_ranges(title or "")
    out = _INLINE_SIZE_GARBAGE_RE.sub("", out)
    out = _SIZE_LABEL_RE.sub("", out)
    out = _TRAILING_BARE_SIZE_RE.sub("", out)
    return _cleanup_spaces(out)


def _strip_title_junk(title: str) -> str:
    """Remove attribute-dump noise. Does not invent selling points (field contract)."""
    if not title:
        return ""
    out = _DOC_SYMBOL_RE.sub(" ", title)
    out = _CLOSURE_DUMP_RE.sub(" ", out)
    out = _FIT_DUMP_RE.sub(" ", out)
    # Fabric wall: drop polyester/spandex/nylon blends; keep searchable materials via separate pass
    # First protect searchable tokens, strip wall, restore is overkill — just strip wall tokens.
    out = _FABRIC_WALL_RE.sub(" ", out)
    out = _COATS_JACKETS_RE.sub("Jacket", out)
    out = re.sub(r"\bPU\b", " ", out)
    # LLM debris: "Cotton- blend. ." / "Black. - blend." / trailing dots
    out = re.sub(r"\.\s*-\s*blend\.?", " ", out, flags=re.I)
    out = re.sub(r"\b(?:cotton|polyester|nylon)\s*[-–]?\s*blend\b\.?", " ", out, flags=re.I)
    out = _strip_dangling_color_dot(out)
    out = re.sub(r"(?:\s*\.){2,}", " ", out)
    out = re.sub(r"\s+\.\s*$", "", out)
    out = re.sub(r"\.\s*\.\s*", " ", out)
    out = _strip_post_type_marketing_spam(out)
    return out


def sanitize_shopping_title(title: str, gpc_path: str = "", gpc_code: str = "") -> str:
    """按品类清洗标题：去掉不合适的塑身词/场景堆砌/说明书垃圾。"""
    if not title:
        return ""
    out = _strip_title_junk(title)
    blob = _path_blob(gpc_path, gpc_code)

    if not allows_tummy_control(gpc_path, gpc_code):
        for pat in _TUMMY_PHRASES:
            out = re.sub(pat, "", out, flags=re.I)

    # 非裙装：去掉 brunch / summer friday / everyday casual 堆砌（裙装可保留 Wedding Guest）
    is_dress = any(k in blob for k in ("dress", "bridal", "gown"))
    if not is_dress:
        for pat in _SCENE_PHRASES:
            out = re.sub(pat, "", out, flags=re.I)
    # Never invent "Casual" after type; also strip trailing Casual pad from assets
    out = _TRAILING_CASUAL_RE.sub(r"\1", out)

    out = _fix_for_remnants(out)
    # Fit remnants created by _fix_for_remnants must still die
    out = _FIT_DUMP_RE.sub(" ", out)
    out = _CLOSURE_DUMP_RE.sub(" ", out)
    out = _cleanup_spaces(out)
    return out

def variant_cue_from_color(color: str) -> str:
    """从颜色名提炼可前置的差异化卖点词。"""
    if not color:
        return ""
    c = color.strip()
    low = c.lower()
    if "stripe" in low:
        return "Stripe Print"
    if "floral" in low or "flower" in low:
        return "Floral Print"
    if "polka" in low or re.search(r"\bdot\b", low):
        return "Polka Dot"
    if "vertical" in low:
        return "Vertical Stripe"
    if low in ("multicolor", "colorful", "mixed"):
        return "Multicolor"
    # 标准单色：作为差异词前置（避免仅靠尾部）
    if len(c) <= 20 and re.match(r"^[A-Za-z][A-Za-z\s\-]+$", c):
        return c
    return ""


def differentiate_variant_title(
    title: str,
    color: str = "",
    size: str = "",
    gpc_path: str = "",
) -> str:
    """DEPRECATED for feed export — kept for tests of cue helper only.

    Field contract: do not mid-insert floral/Plus Size into titles.
    Use polish_feed_title (sanitize + append color/size once).
    """
    return _cleanup_spaces(title or "")


_SIZE_RANGE_RE = re.compile(
    r"\b(?:sizes?\s+)?"
    r"(?:XS|S|M|L|XL|XXL|XXXL|XXXXL|2XL|3XL|4XL|5XL)"
    r"\s*[–\-~/]\s*"
    r"(?:XS|S|M|L|XL|XXL|XXXL|XXXXL|2XL|3XL|4XL|5XL)\b",
    re.I,
)
# "Sizes S M L" / "Size: S, M, L"
_SIZE_LIST_RE = re.compile(
    r"\bSizes?\s*[:：]?\s*(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)"
    r"(?:\s*[,/]?\s*(?:XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)){1,8}\b",
    re.I,
)


def strip_size_ranges(title: str) -> str:
    out = _SIZE_RANGE_RE.sub("", title or "")
    out = _SIZE_LIST_RE.sub("", out)
    return _cleanup_spaces(out)


# Searchable print families for title render (all apparel — not dress-only)
_PRINT_SPAN_RE = re.compile(
    r"\b(?:"
    r"vertical\s+stripes?|curved\s+stripes?|stripes?|striped|"
    r"florals?|flowers?|polka\s+dots?|polka|dots?|"
    r"plaids?|checks?|checked|leopard|camouflage|camo|paisley|"
    r"geometric|argyle|houndstooth|tie[\s-]?dye"
    r")\b",
    re.I,
)
_STYLE_PATTERN_RE = re.compile(r"^style\s*\d+$", re.I)


def searchable_pattern_for_title(pattern: str) -> str:
    """Return a shopper-searchable print label, or '' (never Style N)."""
    p = (pattern or "").strip()
    if not p or _STYLE_PATTERN_RE.match(p):
        return ""
    low = p.lower()
    if "floral" in low or "flower" in low:
        return "Floral"
    if "vertical" in low and "stripe" in low:
        return "Vertical Stripe"
    if "curved" in low and "stripe" in low:
        return "Curved Stripe"
    if "stripe" in low:
        return "Stripe"
    if "polka" in low or re.search(r"\bdots?\b", low):
        return "Polka Dot"
    if "plaid" in low or "check" in low:
        return "Plaid"
    if "leopard" in low:
        return "Leopard"
    if "camo" in low or "camouflage" in low:
        return "Camo"
    if "paisley" in low:
        return "Paisley"
    if "tie" in low and "dye" in low:
        return "Tie Dye"
    # Unknown short token — allow if it looks like a single print word (not Style)
    if re.match(r"^[A-Za-z][A-Za-z\s\-]{1,28}$", p) and "style" not in low:
        return _cleanup_spaces(p.title()) if p.islower() else _cleanup_spaces(p)
    return ""


def _pattern_family_key(label: str) -> str:
    low = (label or "").lower()
    if "floral" in low or "flower" in low:
        return "floral"
    if "stripe" in low:
        return "stripe"
    if "polka" in low or re.search(r"\bdots?\b", low):
        return "polka"
    if "plaid" in low or "check" in low:
        return "plaid"
    if "leopard" in low:
        return "leopard"
    if "camo" in low:
        return "camo"
    return low.split()[0] if low else ""


def _title_covers_pattern(title: str, label: str) -> bool:
    """True only if THIS row's pattern specificity is already in the title."""
    if not title or not label:
        return False
    blob = title.lower()
    lab = label.lower()
    if lab == "vertical stripe":
        return bool(re.search(r"vertical\s+stripes?", blob))
    if lab == "curved stripe":
        return bool(re.search(r"curved\s+stripes?", blob))
    if lab == "stripe":
        # Generic stripe covered by striped/stripe, but not if title already names a subtype only
        if re.search(r"vertical\s+stripes?|curved\s+stripes?", blob):
            return False
        return bool(re.search(r"\bstripes?\b|\bstriped\b", blob))
    if lab == "floral":
        return bool(re.search(r"\b(floral|flower)s?\b", blob))
    if lab == "polka dot":
        return bool(re.search(r"\bpolka\b|\bdots?\b", blob))
    return label.lower() in blob


def _align_skeleton_print(title: str, pattern: str) -> str:
    """If skeleton print family conflicts with THIS row's pattern, replace it."""
    out = _cleanup_spaces(title or "")
    label = searchable_pattern_for_title(pattern)
    if not label or not out:
        return out
    if _title_covers_pattern(out, label):
        return out
    m = _PRINT_SPAN_RE.search(out)
    if not m:
        return out
    # Different print in skeleton → swap for this-row label (variant truth)
    return _cleanup_spaces(out[: m.start()] + label + out[m.end() :])


def append_variant_color_size(
    title: str,
    color: str = "",
    size: str = "",
    pattern: str = "",
) -> str:
    """Append this offer's variant differentiators at most once each.

    High-quality Shopping titles: searchable pattern + color + size for THIS row
    (all product types — not dress-only). Never Style N / dump tokens.
    """
    out = strip_inline_size_mentions(_align_skeleton_print(title or "", pattern))
    color = (color or "").strip()
    size = (size or "").strip()
    label = searchable_pattern_for_title(pattern)
    if label and not _title_covers_pattern(out, label):
        out = f"{out}, {label}"
    if color and color.lower() not in out.lower():
        out = f"{out}, {color}"
    if size and size.lower() not in ("one size", "osfa", ""):
        if not re.search(rf"\bSize\s+{re.escape(size)}\b", out, re.I):
            out = re.sub(rf",?\s*\b{re.escape(size)}\b\s*$", "", out, flags=re.I)
            out = _cleanup_spaces(out)
            out = f"{out}, Size {size}"
    return _cleanup_spaces(out)


def pin_variant_size(title: str, size: str) -> str:
    """Backward-compatible alias — prefer append_variant_color_size."""
    return append_variant_color_size(strip_size_ranges(title), size=size)


def polish_feed_title(
    title: str,
    *,
    color: str = "",
    size: str = "",
    pattern: str = "",
    gpc_path: str = "",
    gpc_code: str = "",
) -> str:
    """Render: sanitize skeleton → strip ranges → pattern+color+size once."""
    cleaned = sanitize_shopping_title(title, gpc_path=gpc_path, gpc_code=gpc_code)
    cleaned = strip_size_ranges(cleaned)
    cleaned = _fix_for_remnants(cleaned)
    return append_variant_color_size(
        cleaned, color=color, size=size, pattern=pattern,
    )
