"""Format mashed 1688/Shopify attribute blobs into readable feed descriptions."""
from __future__ import annotations

import re
from typing import Any

# 常见属性标签（中英）— 粘连时在标签前断行
_ATTR_LABELS = [
    "Attribute", "Color", "Colour", "Style", "Fabric name", "Fabric", "Material",
    "Fit Type", "Fit", "Occasion", "Length", "Waistline", "Closure Type", "Closure",
    "Gender", "Applicable gender", "Size", "Sleeve Length", "Sleeve", "Neckline",
    "Collar type", "Collar", "Pattern", "Popular element", "Function",
    "Seamless construction", "Pack", "Season",
    "颜色", "风格", "面料", "材质", "版型", "场合", "尺码", "袖长", "领型", "图案",
]

_LABEL_ALT = "|".join(re.escape(l) for l in sorted(_ATTR_LABELS, key=len, reverse=True))
_LABEL_BREAK_RE = re.compile(
    rf"(?<![\n])(?<![\n\s:])(?P<label>{_LABEL_ALT})\s*[:：]",
    re.I,
)
_GLUED_LABEL_RE = re.compile(
    rf"(?P<pre>[a-zA-Z0-9%\.\)])(?P<label>{_LABEL_ALT})\s*[:：]",
    re.I,
)

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# Size-chart table start (1688 mashed tables after attribute lines)
_SIZE_CHART_START_RE = re.compile(
    r"(?im)^(?:"
    r"Size:\s*unit:\s*cm|"
    r"Size\s*$|"
    r"尺码表|"
    r"尺码\s*[:：]?\s*$|"
    r"(?:Waist|Bust|Hip|Chest|Shoulder|Length)/cm\s*$"
    r")"
)
_SIZE_DIM_LINE_RE = re.compile(
    r"(?i)^(?:Waist|Bust|Hip|Chest|Shoulder|Length|Sleeve)(?:\s*/\s*cm)?\s*$"
)
_PURE_SIZE_TOKEN_RE = re.compile(
    r"(?i)^(XX?S|XX?L|XXX?L|XXXXL|S|M|L|XL|\d{2,3}|\d+XL)$"
)

# Chinese attribute labels → English (feed prefers EN for US/EU Shopping)
_ZH_LABEL_MAP = {
    "颜色": "Color",
    "风格": "Style",
    "面料": "Fabric",
    "材质": "Material",
    "版型": "Fit",
    "场合": "Occasion",
    "尺码": "Size",
    "袖长": "Sleeve Length",
    "领型": "Collar",
    "图案": "Pattern",
    "适用性别": "Gender",
    "性别": "Gender",
    "功能": "Function",
    "季节": "Season",
}


def cjk_ratio(text: str) -> float:
    """Fraction of CJK chars among letters+digits+CJK (ignore whitespace/punct)."""
    if not text:
        return 0.0
    cjk = 0
    significant = 0
    for ch in str(text):
        if "\u4e00" <= ch <= "\u9fff":
            cjk += 1
            significant += 1
        elif ch.isalnum():
            significant += 1
    if significant == 0:
        return 0.0
    return cjk / significant


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(str(text or "")))


def translate_zh_labels(text: str) -> str:
    """Replace common Chinese attribute labels with English equivalents."""
    if not text:
        return ""
    out = str(text)
    for zh, en in sorted(_ZH_LABEL_MAP.items(), key=lambda x: -len(x[0])):
        out = re.sub(rf"{re.escape(zh)}\s*[:：]", f"{en}: ", out)
    return out


def truncate_size_chart(text: str) -> str:
    """Drop mashed size-measurement tables; keep attribute lines + short note."""
    if not text or not str(text).strip():
        return ""
    lines = str(text).splitlines()
    cut_at = None
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            continue
        if _SIZE_CHART_START_RE.match(s):
            # lone "Size" only counts if next non-empty looks like chart header/body
            if re.match(r"(?i)^Size\s*$", s):
                nxt = next((ln.strip() for ln in lines[i + 1 :] if ln.strip()), "")
                if not (
                    _SIZE_DIM_LINE_RE.match(nxt)
                    or re.match(r"(?i)^Size:\s*unit", nxt)
                    or _PURE_SIZE_TOKEN_RE.match(nxt)
                ):
                    continue
            cut_at = i
            break
        if _SIZE_DIM_LINE_RE.match(s):
            cut_at = i
            break
    if cut_at is None:
        return str(text).strip()

    kept = [ln for ln in lines[:cut_at] if ln.strip()]
    # Drop redundant "Size: S, M, L..." list right above the table (offer size is in g:size)
    while kept:
        last = kept[-1].strip()
        if re.match(r"(?i)^Size:\s*.+", last) and "," in last:
            kept.pop()
            continue
        break
    note = "Size chart: see product page."
    if kept and kept[-1].strip().lower() == note.lower():
        return "\n".join(kept).strip()
    kept.append(note)
    return "\n".join(kept).strip()


def format_product_description(desc: str, max_chars: int = 5000) -> str:
    """把 Color:BlueStyle:… / 表格残片格式化成逐行属性。"""
    if not desc or not str(desc).strip():
        return ""
    text = str(desc)

    # HTML 残留
    text = re.sub(r"<[^>]+>", "\n", text)
    text = text.replace("\xa0", " ").replace("&nbsp;", " ")
    text = text.replace("：", ": ").replace("，", ", ")

    # 粘连：BlueStyle: → Blue\nStyle:
    text = _GLUED_LABEL_RE.sub(r"\g<pre>\n\g<label>: ", text)
    # 标签前强制换行（已换行的不重复）
    text = _LABEL_BREAK_RE.sub(r"\n\g<label>: ", text)

    # Color:Blue → Color: Blue
    text = re.sub(rf"({_LABEL_ALT})\s*[:：]\s*", r"\1: ", text, flags=re.I)

    # 压缩空白行，保留单行属性
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line:
            continue
        lines.append(line)

    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    out = truncate_size_chart(out)

    if max_chars and len(out) > max_chars:
        cut = out[:max_chars]
        nl = cut.rfind("\n")
        if nl > max_chars // 2:
            out = cut[:nl].rstrip()
        else:
            out = cut.rstrip()
    return out


def prepare_feed_description(
    desc: str,
    *,
    max_chars: int = 5000,
    heavy_cjk_threshold: float = 0.35,
) -> tuple[str, dict[str, Any]]:
    """Format + EN labels; report whether heavy CJK remains.

    Returns (text, meta) where meta may include:
      changed, had_cjk, still_cjk_ratio, heavy_cjk, label_translated
    """
    raw = str(desc or "")
    meta: dict[str, Any] = {
        "changed": False,
        "had_cjk": has_cjk(raw),
        "still_cjk_ratio": 0.0,
        "heavy_cjk": False,
        "label_translated": False,
    }
    if not raw.strip():
        return "", meta

    labeled = translate_zh_labels(raw)
    if labeled != raw:
        meta["label_translated"] = True

    # Best-effort: translate known material/color tokens (local maps — avoid circular import)
    _MAT = {
        "聚酯纤维": "Polyester", "涤纶": "Polyester", "氨纶": "Spandex",
        "纯棉": "Cotton", "棉": "Cotton", "真丝": "Silk", "亚麻": "Linen",
        "尼龙": "Nylon", "蕾丝": "Lace", "雪纺": "Chiffon", "牛仔": "Denim",
    }
    _COL = {
        "黑色": "Black", "白色": "White", "红色": "Red", "蓝色": "Blue",
        "绿色": "Green", "黄色": "Yellow", "粉色": "Pink", "灰色": "Grey",
        "藏青": "Navy", "米色": "Beige",
    }
    for zh, en in sorted(_MAT.items(), key=lambda x: -len(x[0])):
        if zh in labeled:
            labeled = labeled.replace(zh, en)
    for zh, en in sorted(_COL.items(), key=lambda x: -len(x[0])):
        if zh in labeled:
            labeled = labeled.replace(zh, en)

    formatted = format_product_description(labeled, max_chars=max_chars)
    ratio = cjk_ratio(formatted)
    meta["still_cjk_ratio"] = ratio
    meta["heavy_cjk"] = ratio >= heavy_cjk_threshold
    meta["changed"] = formatted != raw.strip()
    return formatted, meta


def english_summary_from_fields(
    title: str = "",
    material: str = "",
    color: str = "",
    size: str = "",
) -> str:
    """Short EN fallback when description is mostly Chinese."""
    parts: list[str] = []
    t = (title or "").strip()
    if t:
        parts.append(t if t.endswith(".") else f"{t}.")
    mat = (material or "").strip()
    if mat and not has_cjk(mat):
        parts.append(f"Material: {mat}.")
    col = (color or "").strip()
    if col and not has_cjk(col):
        parts.append(f"Color: {col}.")
    sz = (size or "").strip()
    if sz and sz.lower() not in ("one size", "nan") and not has_cjk(sz):
        parts.append(f"Size: {sz}.")
    if not parts:
        return "Product details available on the store page."
    return " ".join(parts)
