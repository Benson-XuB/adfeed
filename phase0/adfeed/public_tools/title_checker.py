"""Rule-based Google Shopping title checker for marketing-site tools.

Diagnoses missing shopping signals and strips marketplace noise.
Does not invent brand, GTIN, material, or other attributes.
"""

from __future__ import annotations

import re
from typing import Any

from adfeed.public_tools.feed_checker import TITLE_NOISE_RE, TITLE_SOFT_LIMIT

DISCLAIMER = "Suggestion only — do not invent brand or GTIN."

AUDIENCE_RE = re.compile(
    r"\b(women'?s?|men'?s?|kids?|boys?|girls?|unisex|baby|toddler)\b",
    re.I,
)
MATERIAL_RE = re.compile(
    r"\b(cotton|linen|silk|wool|polyester|nylon|leather|denim|"
    r"cashmere|velvet|satin|rayon|modal|spandex|fleece|knit|woven)\b",
    re.I,
)
STYLE_RE = re.compile(
    r"\b(midi|maxi|mini|casual|formal|loose|slim|fitted|oversized|"
    r"a-?line|wrap|bodycon|boho|vintage|classic|sporty|relaxed)\b",
    re.I,
)
COLOR_RE = re.compile(
    r"\b(black|white|red|blue|green|yellow|pink|purple|orange|brown|"
    r"gray|grey|beige|navy|khaki|cream|ivory|burgundy|olive|teal|"
    r"coral|maroon|gold|silver|multicolor|multi-?color)\b",
    re.I,
)
# Avoid matching the possessive "s" in Women's / Men's (apostrophe is a non-word char).
SIZE_RE = re.compile(
    r"(?<!')\b(xxs|xs|s|m|l|xl|xxl|xxxl|2xl|3xl|4xl|"
    r"one\s*size|os|"
    r"\d{1,2}(?:\.\d)?)\b",
    re.I,
)

# Product-ish tokens — if almost none, title is too weak to diagnose.
PRODUCT_HINT_RE = re.compile(
    r"\b(dress|skirt|shirt|tee|t-?shirt|top|blouse|jacket|coat|pants|"
    r"jeans|shorts|sweater|hoodie|shoes?|boots?|bag|hat|socks?|"
    r"swimsuit|romper|jumpsuit|cardigan|vest|leggings?)\b",
    re.I,
)

ISSUE_META: dict[str, tuple[str, str]] = {
    "too_long": (
        "Title may be too long",
        f"Shopping cards often truncate around {TITLE_SOFT_LIMIT} characters. "
        "Lead with audience, product, and key attributes shoppers search for.",
    ),
    "noisy_words": (
        "Marketplace / promo wording",
        "Drop phrases like Free Shipping, Hot Sale, New Arrival — they waste card space "
        "and do not help shoppers identify the product.",
    ),
    "missing_audience": (
        "Missing audience",
        "Add who it is for when known (e.g. Women's, Men's) — do not invent one.",
    ),
    "missing_material": (
        "Missing material",
        "If the fabric is known (linen, cotton, …), include it once. Do not invent material.",
    ),
    "missing_style": (
        "Missing style / cut",
        "A short style cue (midi, loose, A-line) helps when you already know it from the product.",
    ),
    "missing_color": (
        "Missing color",
        "Include the real color for this variant when known. Keep pattern/style out of color.",
    ),
    "missing_size": (
        "Missing size",
        "Include the size for this variant when known (S, M, XL, …).",
    ),
}


def _issue(code: str) -> dict[str, str]:
    label, advice = ISSUE_META[code]
    return {"code": code, "label": label, "advice": advice}


def _strip_noise(title: str) -> str:
    cleaned = TITLE_NOISE_RE.sub(" ", title)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,;/-")
    return cleaned


def _detect_present(title: str) -> dict[str, bool]:
    return {
        "audience": bool(AUDIENCE_RE.search(title)),
        "material": bool(MATERIAL_RE.search(title)),
        "style": bool(STYLE_RE.search(title)),
        "color": bool(COLOR_RE.search(title)),
        "size": bool(SIZE_RE.search(title)),
    }


def _verdict(
    *,
    title: str,
    issues: list[dict[str, str]],
    present: dict[str, bool],
) -> str:
    if not title.strip():
        return "weak"
    tokens = re.findall(r"[A-Za-z0-9']+", title)
    if len(tokens) < 2 and not PRODUCT_HINT_RE.search(title):
        return "weak"
    signal_count = sum(1 for v in present.values() if v)
    if signal_count == 0 and not PRODUCT_HINT_RE.search(title):
        return "weak"
    hard = {i["code"] for i in issues} & {"too_long", "noisy_words"}
    if hard:
        return "improve"
    missing = [i for i in issues if i["code"].startswith("missing_")]
    if len(missing) >= 3:
        return "improve"
    if missing:
        return "improve"
    return "ok"


def analyze_title(raw: str) -> dict[str, Any]:
    title = (raw or "").strip()
    issues: list[dict[str, str]] = []

    if TITLE_NOISE_RE.search(title):
        issues.append(_issue("noisy_words"))
    if len(title) > TITLE_SOFT_LIMIT:
        issues.append(_issue("too_long"))

    present = _detect_present(title)
    for key in ("audience", "material", "style", "color", "size"):
        if not present[key]:
            issues.append(_issue(f"missing_{key}"))

    suggested = _strip_noise(title) or title
    # Soft re-trim if still over soft limit after noise strip (keep word order).
    if len(suggested) > TITLE_SOFT_LIMIT:
        words = suggested.split()
        trimmed: list[str] = []
        for w in words:
            candidate = " ".join(trimmed + [w])
            if trimmed and len(candidate) > TITLE_SOFT_LIMIT:
                break
            trimmed.append(w)
        if trimmed:
            suggested = " ".join(trimmed)

    verdict = _verdict(title=title, issues=issues, present=present)

    return {
        "ok": True,
        "input": title,
        "verdict": verdict,
        "issues": issues,
        "present": present,
        "suggested_title": suggested,
        "disclaimer": DISCLAIMER,
    }
