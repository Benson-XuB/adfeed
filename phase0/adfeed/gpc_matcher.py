"""AdFeed AI — GPC (Google Product Category) 类目匹配引擎

Phase 0: 混合方案 — 关键词快速匹配 + LLM 兜底确认
- 无需 Embedding API，无需本地大模型，轻量快速
- 从 taxonomy 文件中按关键词优先级匹配
- 低置信度时触发 LLM 二次确认
"""

import re
import json
from pathlib import Path

from .config import (
    TAXONOMY_FILE, GPC_CONFIDENCE_THRESHOLD,
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL, PROMPTS_DIR,
)

_taxonomy_entries: list[dict] = None
_taxonomy_lookup: dict[str, list[int]] = {}  # keyword → [index]


# 1688 常见品类中文关键词到英文的映射（优先级权重）
CATEGORY_KEYWORD_MAP = {
    "T恤": {"keys": ["t-shirt", "shirt", "top", "tee"], "weight": 1.5},
    "衬衫": {"keys": ["shirt", "dress shirt", "button-up"], "weight": 1.2},
    "连衣裙": {"keys": ["dress", "dresses"], "weight": 1.5},
    "裙子": {"keys": ["skirt", "skirts"], "weight": 1.5},
    "外套": {"keys": ["jacket", "coat", "outerwear"], "weight": 1.3},
    "羽绒服": {"keys": ["jacket", "coat", "down coat"], "weight": 1.4},
    "裤子": {"keys": ["pants", "trousers", "jeans", "shorts"], "weight": 1.5},
    "鞋": {"keys": ["shoes", "footwear", "sneakers", "boots"], "weight": 1.5},
    "运动鞋": {"keys": ["athletic shoes", "running shoes", "sneakers"], "weight": 1.5},
    "耳机": {"keys": ["headphones", "earbuds", "earphones", "audio"], "weight": 1.5},
    "蓝牙耳机": {"keys": ["earbuds", "headphones", "wireless", "bluetooth audio"], "weight": 1.6},
    "充电器": {"keys": ["charger", "phone charger", "car charger"], "weight": 1.4},
    "手机壳": {"keys": ["phone case", "cell phone case"], "weight": 1.6},
    "手机支架": {"keys": ["phone stand", "mount", "holder"], "weight": 1.4},
    "智能手表": {"keys": ["smartwatch", "wearable", "fitness tracker"], "weight": 1.6},
    "台灯": {"keys": ["lamp", "desk lamp", "lighting", "reading lamp"], "weight": 1.5},
    "灯具": {"keys": ["lamp", "lighting", "light fixture"], "weight": 1.3},
    "杯子": {"keys": ["cup", "mug", "drinkware"], "weight": 1.5},
    "咖啡杯": {"keys": ["coffee", "mug", "cup", "drinkware"], "weight": 1.6},
    "马克杯": {"keys": ["mug", "cup", "drinkware"], "weight": 1.6},
    "枕头": {"keys": ["pillow", "bedding"], "weight": 1.6},
    "收纳箱": {"keys": ["storage box", "storage bin", "storage basket", "organizer"], "weight": 1.5},
    "地垫": {"keys": ["mat", "rug", "door mat", "bath mat"], "weight": 1.5},
    "门垫": {"keys": ["door mat", "rug", "mat", "entrance mat"], "weight": 1.6},
    "精华": {"keys": ["serum", "skincare", "facial", "treatment"], "weight": 1.4},
    "护肤品": {"keys": ["skincare", "moisturizer", "facial", "beauty"], "weight": 1.4},
    "面膜": {"keys": ["mask", "facial mask", "skincare"], "weight": 1.6},
    "洗发水": {"keys": ["shampoo", "hair care", "conditioner"], "weight": 1.6},
    "牙刷": {"keys": ["toothbrush", "oral care", "electric toothbrush"], "weight": 1.6},
    "化妆刷": {"keys": ["makeup brush", "cosmetic brush", "beauty tool"], "weight": 1.6},
    "收纳": {"keys": ["storage", "organizer", "basket", "bin", "box"], "weight": 1.2},
    "沙发": {"keys": ["sofa", "couch", "furniture"], "weight": 1.5},
    "桌子": {"keys": ["desk", "table", "furniture"], "weight": 1.5},
    "椅子": {"keys": ["chair", "seat", "furniture"], "weight": 1.5},
    "床": {"keys": ["bed", "bedroom furniture"], "weight": 1.5},
    "窗帘": {"keys": ["curtain", "window treatment", "drapery"], "weight": 1.5},
    "地毯": {"keys": ["rug", "carpet", "floor covering"], "weight": 1.5},
    "玩具": {"keys": ["toy", "toys", "games"], "weight": 1.3},
    "宠物": {"keys": ["pet supplies", "pet", "dog", "cat"], "weight": 1.4},
    "运动": {"keys": ["sporting goods", "athletic", "exercise", "fitness"], "weight": 1.2},
    "瑜伽": {"keys": ["yoga", "exercise", "fitness", "mat"], "weight": 1.5},
    "户外": {"keys": ["outdoor", "camping", "hiking", "sports"], "weight": 1.3},
    "厨房": {"keys": ["kitchen", "cooking", "cookware", "bakeware"], "weight": 1.3},
    "浴室": {"keys": ["bathroom", "bath", "shower"], "weight": 1.4},
    "花园": {"keys": ["garden", "outdoor", "patio", "plant"], "weight": 1.4},
    "汽车": {"keys": ["vehicle", "car", "automotive"], "weight": 1.3},
    "工具": {"keys": ["tool", "hardware", "equipment"], "weight": 1.2},
    "珠宝": {"keys": ["jewelry", "accessories", "necklace", "bracelet", "ring"], "weight": 1.5},
    "手表": {"keys": ["watch", "wristwatch", "timepiece"], "weight": 1.5},
    "包": {"keys": ["bag", "handbag", "backpack", "wallet", "purse"], "weight": 1.4},
    "帽子": {"keys": ["hat", "cap", "headwear"], "weight": 1.5},
    "围巾": {"keys": ["scarf", "accessories", "winter wear"], "weight": 1.5},
    "手套": {"keys": ["gloves", "mittens", "hand wear"], "weight": 1.5},
    "袜子": {"keys": ["socks", "hosiery", "underwear"], "weight": 1.5},
    "内衣": {"keys": ["underwear", "lingerie", "bra", "intimates"], "weight": 1.5},
    "泳衣": {"keys": ["swimwear", "swimsuit", "bikini"], "weight": 1.6},
    "睡衣": {"keys": ["sleepwear", "pajamas", "nightwear"], "weight": 1.5},
    "电脑": {"keys": ["computer", "laptop", "pc", "accessories"], "weight": 1.3},
    "手机": {"keys": ["cell phone", "phone", "mobile", "smartphone"], "weight": 1.3},
    "平板": {"keys": ["tablet", "ipad", "computer"], "weight": 1.4},
    "相机": {"keys": ["camera", "camcorder", "photography"], "weight": 1.5},
    "食品": {"keys": ["food", "beverage", "grocery", "snack"], "weight": 1.3},
    "饮料": {"keys": ["beverage", "drink", "coffee", "tea"], "weight": 1.4},
    "茶": {"keys": ["tea", "beverage", "drink"], "weight": 1.5},
    "咖啡": {"keys": ["coffee", "beverage", "drink"], "weight": 1.5},
}


def _parse_taxonomy() -> list[dict]:
    """解析 Google taxonomy 文件"""
    global _taxonomy_entries
    if _taxonomy_entries is not None:
        return _taxonomy_entries

    entries = []
    with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(" - ", 1)
            if len(parts) == 2:
                code, path = parts
                entries.append({
                    "gpc_code": code.strip(),
                    "path_en": path.strip(),
                    "path_lower": path.strip().lower(),
                })
    _taxonomy_entries = entries
    print(f"[GPCMatcher] 加载 taxonomy: {len(entries)} 个类目")
    return entries


def _keyword_score(entry: dict, keywords: list[str], weights: dict[str, float]) -> float:
    """计算一个 taxonomy 条目对给定关键词的匹配得分"""
    score = 0.0
    path = entry["path_lower"]

    for kw in keywords:
        kw_lower = kw.lower()
        if kw_lower in path:
            # 越深的层级匹配权重越高
            depth = path.count(">")
            weight = weights.get(kw, 1.0)
            # 完全匹配最后一级加额外分
            if path.endswith(kw_lower) or path.endswith(kw_lower + "s"):
                score += 3.0 * weight
            else:
                score += 1.0 * weight * (1 + depth * 0.1)

    return score


def _extract_keywords(title: str, category: str, material: str) -> list[str]:
    """从商品信息中提取关键词"""
    keywords = []

    # 从原始分类中提取
    cat_parts = re.split(r'[>/\-\s,]+', category)
    for part in cat_parts:
        part = part.strip().lower()
        if part and part not in ("", "&", "and") and not part.isdigit() and len(part) >= 2:
            keywords.append(part)

    # 从标题中提取（跳过纯数字、年份、单字符和营销词）
    title_parts = re.split(r'[,\s，]+', title)
    skip_words = {"2024", "2025", "2026", "new", "hot", "free", "sale", "cheap", "🔥"}
    for part in title_parts:
        part = part.strip().lower()
        if len(part) >= 2 and part not in skip_words and not part.isdigit():
            keywords.append(part)
        if len(keywords) >= 10:
            break

    # 从中文关键词映射表中获取英文关键词
    for cn_kw, mapping in CATEGORY_KEYWORD_MAP.items():
        if cn_kw in title or cn_kw in category:
            keywords.extend(mapping["keys"])

    # 材质关键词
    if material and material not in ("", "N/A"):
        keywords.append(material.lower())

    return list(set(keywords))  # 去重


def match(title: str, category: str = "", material: str = "",
          attributes: dict = None) -> dict:
    """匹配 GPC 类目

    策略：关键词匹配 + 低置信度 LLM 兜底
    """
    entries = _parse_taxonomy()
    keywords = _extract_keywords(title, category, material)

    if not keywords:
        return {"gpc_code": "", "gpc_path": "", "confidence": 0.0, "source": "no_keywords"}

    # 为每个类目计算得分
    scored = []
    for i, entry in enumerate(entries):
        s = _keyword_score(entry, keywords, {})
        if s > 0:
            scored.append((s, i, entry))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        # 无关键词匹配 → LLM 直接分类
        return _llm_classify(title, category, material, entries[:200])

    top_score, top_idx, top_entry = scored[0]

    # 归一化置信度（原始分 / 理论最高分）
    normalized_confidence = min(top_score / 10.0, 0.99)

    result = {
        "gpc_code": top_entry["gpc_code"],
        "gpc_path": top_entry["path_en"],
        "confidence": round(normalized_confidence, 4),
        "source": "keyword",
    }

    # 低置信度 → LLM 确认
    if normalized_confidence < GPC_CONFIDENCE_THRESHOLD:
        candidates = [
            entries[idx] for _, idx, _ in scored[:5]
        ]
        result = _llm_confirm_candidates(title, category, material, candidates)
        result["source"] = "llm_confirm"

    return result


def _llm_classify(title: str, category: str, material: str,
                  sample_entries: list[dict]) -> dict:
    """关键词匹配失败时，直接用 LLM 从顶层类目中分类"""
    from openai import OpenAI

    # 只发送顶层类目（深度 ≤ 2）减少 token
    top_levels = []
    for e in sample_entries:
        depth = e["path_en"].count(">")
        if depth <= 2 and e not in top_levels:
            top_levels.append(e)
        if len(top_levels) >= 50:
            break

    cats_text = "\n".join(f"- {e['gpc_code']}: {e['path_en']}" for e in top_levels)

    prompt = f"""You are a Google Product Category classifier.
From the following categories, pick the SINGLE most appropriate GPC code for this product.

Product:
- Title: {title}
- Source Category: {category}
- Material: {material}

Categories (top level only):
{cats_text}

Output ONLY the GPC code number. Example: 2271"""

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10, temperature=0.1,
    )
    answer = response.choices[0].message.content.strip()

    # 查找匹配的条目
    for e in entries if (entries := _taxonomy_entries) else []:
        if e["gpc_code"] in answer or e["gpc_code"] == answer:
            return {"gpc_code": e["gpc_code"], "gpc_path": e["path_en"],
                    "confidence": 0.75, "source": "llm_classify"}

    return {"gpc_code": answer, "gpc_path": "", "confidence": 0.5, "source": "llm_classify"}


def _llm_confirm_candidates(title: str, category: str, material: str,
                            candidates: list[dict]) -> dict:
    """LLM 从候选类目中确认最佳匹配"""
    from openai import OpenAI

    candidates_text = "\n".join(
        f"{i+1}. {c['gpc_code']} — {c['path_en']}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""Pick the best Google Product Category code for this product.

Product: title="{title}", category="{category}", material="{material}"

Candidates:
{candidates_text}

Output ONLY the GPC code number. Example: 2271"""

    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
    response = client.chat.completions.create(
        model=LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=10, temperature=0.1,
    )
    answer = response.choices[0].message.content.strip()

    for c in candidates:
        if c["gpc_code"] in answer:
            return {"gpc_code": c["gpc_code"], "gpc_path": c["path_en"],
                    "confidence": 0.80, "source": "llm_confirm"}

    # 兜底：返回第一个候选
    return {"gpc_code": candidates[0]["gpc_code"], "gpc_path": candidates[0]["path_en"],
            "confidence": 0.60, "source": "llm_fallback"}


def load_taxonomy(force_rebuild: bool = False) -> tuple[list[dict], None]:
    """加载 taxonomy（Phase 0 纯内存方案，不需要 FAISS 索引）"""
    entries = _parse_taxonomy()
    return entries, None
