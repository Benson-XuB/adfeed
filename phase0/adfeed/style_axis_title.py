"""Style-axis title skeletons for opaque Style/Design options (any catalog).

When Shopify packs different garments under Style 1 / Design A / 款式2, we already
split item_group_id. Titles must also differ with searchable cues — never "Style 1".
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

from .attribute_normalizer import opaque_style_axis_key

_BANNED_IN_CUE = re.compile(
    r"\b(?:style|design|type)\s*[-_]?\s*\d+\b|\b款式\s*\d+\b",
    re.I,
)


def collect_style_axis_profiles(
    variants: list[dict],
    *,
    description: str = "",
    title: str = "",
) -> dict[str, dict[str, Any]]:
    """Group variants by opaque style axis → {style_key: {image_url, raw, sizes}}."""
    profiles: dict[str, dict[str, Any]] = {}
    for v in variants or []:
        raw = str(v.get("color") or v.get("color_raw") or "").strip()
        key = opaque_style_axis_key(raw)
        if not key:
            continue
        slot = profiles.setdefault(
            key,
            {"raw": raw, "image_url": "", "sizes": [], "title": title, "description": description},
        )
        img = (v.get("feed_image_url") or v.get("image_url") or "").strip()
        if img and not slot["image_url"]:
            slot["image_url"] = img
        sz = str(v.get("size") or "").strip()
        if sz and sz not in slot["sizes"]:
            slot["sizes"].append(sz)
    return profiles


def _clean_skeleton(text: str) -> str:
    raw = (text or "").strip()
    if not raw:
        return ""
    # Entire skeleton discarded if it still names opaque option codes
    if _BANNED_IN_CUE.search(raw):
        return ""
    out = re.sub(r"\s+", " ", raw).strip(" ,|-")
    return out


def apply_style_skeleton(base_title: str, style_skeleton: str) -> str:
    """Use style-specific skeleton when present (field contract: no Style N dump)."""
    sk = _clean_skeleton(style_skeleton)
    if not sk:
        return (base_title or "").strip()
    return sk


def infer_style_title_skeletons(
    *,
    product_title: str,
    description: str,
    gpc_path: str = "",
    profiles: dict[str, dict[str, Any]],
    base_skeleton: str = "",
    llm_fn=None,
) -> dict[str, str]:
    """Return {style_key: shopping skeleton without color/size} for each opaque style.

    High-quality: searchable differences (Zip, Lace-Up, Belted…) — never Style N.
    llm_fn optional for tests; default calls DashScope (vision if images exist).
    """
    if len(profiles) < 2:
        return {}

    if llm_fn is None:
        llm_fn = _default_llm_style_skeletons

    try:
        raw = llm_fn(
            product_title=product_title or "",
            description=(description or "")[:2500],
            gpc_path=gpc_path or "",
            profiles=profiles,
            base_skeleton=base_skeleton or "",
        )
    except Exception as e:
        print(f"  [StyleTitle] LLM failed: {e}")
        return {}

    out: dict[str, str] = {}
    if not isinstance(raw, dict):
        return {}
    for key in profiles:
        sk = _clean_skeleton(str(raw.get(key) or ""))
        if sk and not _BANNED_IN_CUE.search(sk):
            out[key] = sk
    return out


def _default_llm_style_skeletons(
    *,
    product_title: str,
    description: str,
    gpc_path: str,
    profiles: dict[str, dict[str, Any]],
    base_skeleton: str,
) -> dict[str, str]:
    from openai import OpenAI
    from .config import DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL

    if not DASHSCOPE_API_KEY or DASHSCOPE_API_KEY == "sk-your-api-key-here":
        return {}

    keys = list(profiles.keys())
    lines = []
    for k, meta in profiles.items():
        lines.append(
            f"- key={k} raw_option={meta.get('raw')!r} "
            f"image={meta.get('image_url') or 'none'} sizes={meta.get('sizes')}"
        )
    prompt = f"""You write Google Shopping title SKELETONS for apparel (US English).

This Shopify product packs DIFFERENT garments under opaque options (Style 1 / Design A…).
We already split item groups. You must write a DISTINCT skeleton per option key.

Product title: {product_title}
GPC: {gpc_path or "n/a"}
Shared base skeleton (may be wrong for some styles): {base_skeleton or "n/a"}
Description (may include size charts per style):
{description[:2000]}

Options:
{chr(10).join(lines)}

Rules:
- Output JSON object ONLY: keys must be exactly {json.dumps(keys)}
- Value = short shopping skeleton: Gender + ≤2 searchable features + product type
- Features must be shopper-searchable (Zip, Lace-Up, Belted, Bomber, V-Neck, Cropped…)
- Use BOTH feature slots when images clearly show two differences
- Look at each image URL when provided — use VISIBLE differences
- NEVER write Style 1, Style 2, Design A, 款式, or option codes
- NEVER pad with summer/vintage/elegant/Casual/Everyday unless clearly visible
- Do NOT include color or size (renderer adds them)
- Do NOT invent GTIN/brand
- Skeletons for different keys MUST differ

Example shape: {{"style-1": "Women's Lace-Up Belted V-Neck Jacket", "style-2": "Women's Zip Front Bomber Jacket"}}
"""

    vl_model = os.getenv("ADFEED_STYLE_VL_MODEL", "qwen-vl-plus")
    text_model = os.getenv("ADFEED_STYLE_LLM_MODEL", LLM_MODEL)
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

    has_images = any((m.get("image_url") or "").startswith("http") for m in profiles.values())
    if has_images:
        content: list[dict] = [{"type": "text", "text": prompt}]
        for k, meta in profiles.items():
            url = (meta.get("image_url") or "").strip()
            if url.startswith("http"):
                content.append({"type": "text", "text": f"Image for key {k}:"})
                content.append({"type": "image_url", "image_url": {"url": url}})
        resp = client.chat.completions.create(
            model=vl_model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            max_tokens=400,
        )
        model_used = vl_model
    else:
        resp = client.chat.completions.create(
            model=text_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=400,
        )
        model_used = text_model

    text = (resp.choices[0].message.content or "").strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    data = json.loads(text)
    print(f"  [StyleTitle] skeletons via {model_used} for {len(data)} keys")
    return data if isinstance(data, dict) else {}
