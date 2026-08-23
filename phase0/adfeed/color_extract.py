"""Extract GMC color from title/description: dictionary first, then LLM → Multicolor."""
from __future__ import annotations

import hashlib
import re

_COLOR_CACHE: dict[str, str] = {}

_COLOR_PROMPT = """Analyze the product title and description below.
Extract the primary product color as a single English GMC color name
(e.g. Black, White, Red, Navy, Multicolor).
Translate Chinese color words to English.
If no color can be determined, return exactly Multicolor.
Return ONLY the color word(s), no punctuation or explanation.

Title: {title}
Description: {description}
"""


def _dict_color(title: str, description: str = "") -> str:
    """Dictionary / resolve path; returns real color or empty (never Multicolor)."""
    try:
        from .attribute_normalizer import resolve_gmc_color, _canonical_color_token
    except Exception:
        return ""

    blob = f"{title or ''} {re.sub(r'<[^>]+>', ' ', description or '')}"
    hit = _canonical_color_token(blob)
    if hit and hit != "Multicolor":
        return hit

    resolved = resolve_gmc_color(
        "",
        description=description or "",
        title=title or "",
    )
    if resolved and resolved != "Multicolor":
        return resolved
    return ""


def _llm_color(prompt: str) -> str:
    """Call DashScope-compatible chat API; patchable in tests."""
    try:
        from .config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL
        from openai import OpenAI
    except Exception:
        return "Multicolor"

    if not DASHSCOPE_API_KEY:
        return "Multicolor"

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You extract product colors. Output only a color name.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        max_tokens=16,
    )
    raw = (response.choices[0].message.content or "").strip()
    # First line only
    raw = raw.split("\n")[0].strip().strip('"\'.,;:')
    return raw or "Multicolor"


def extract_color_from_text(title: str, description: str = "") -> str:
    """Return English GMC color from title+description; Multicolor if none."""
    dict_hit = _dict_color(title, description)
    if dict_hit:
        return dict_hit

    cache_key = hashlib.sha1(
        f"{title or ''}\n{description or ''}".encode("utf-8", errors="ignore")
    ).hexdigest()
    if cache_key in _COLOR_CACHE:
        return _COLOR_CACHE[cache_key]

    prompt = _COLOR_PROMPT.format(
        title=title or "N/A",
        description=(description or "N/A")[:800],
    )
    try:
        result = (_llm_color(prompt) or "").strip()
    except Exception:
        result = ""

    if not result:
        result = "Multicolor"
    if result.lower() == "multicolor":
        result = "Multicolor"
    elif result and result[0].islower():
        result = result.title()

    _COLOR_CACHE[cache_key] = result
    return result


def clear_color_cache() -> None:
    """Test helper."""
    _COLOR_CACHE.clear()
