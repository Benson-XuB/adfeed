"""AdFeed AI — GPC 类目匹配引擎 v2.0（方案C：关键词 + LLM 兜底）

匹配策略：
1. 从产品标题/分类/材质提取英文关键词
2. 在 SQLite gpc_taxonomy 表中做 LIKE 模糊匹配（零 API 成本，<10ms）
3. 高置信度（≥0.65）→ 直接返回 GPC ID
4. 低置信度 → 取 Top 5 候选，调 LLM 确认（~1-3s，¥0.002/次）

接口签名与 v1 完全兼容，pipeline 零改动。
"""

import re
import json
from pathlib import Path

from .config import (
    GPC_CONFIDENCE_THRESHOLD,
    DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL, LLM_MODEL, PROMPTS_DIR,
)
from . import gpc_db


# ─────────────────────────────────────────────
# 中文品类 → 英文关键词映射（用于 1688/中文标题）
# ─────────────────────────────────────────────

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
    "水杯": {"keys": ["water bottle", "drinkware", "water"], "weight": 1.6},
    "水壶": {"keys": ["kettle", "water bottle", "thermos"], "weight": 1.5},
}


# ─────────────────────────────────────────────
# 关键词提取
# ─────────────────────────────────────────────

# 常见材质/形容词（不应作为品类匹配关键词）
_MATERIAL_WORDS = {
    "stainless", "steel", "cotton", "polyester", "nylon", "leather", "rubber",
    "plastic", "wooden", "metal", "ceramic", "glass", "silicone", "aluminum",
    "insulated", "lightweight", "breathable", "waterproof", "portable",
    "adjustable", "foldable", "reusable", "electric", "wireless", "digital",
}

# 强品类词：标题里出现时应压过装饰/部件词（如 zipper on jeans）
_PRODUCT_TYPE_WORDS = {
    "jeans": ["pants", "jeans", "denim"],  # taxonomy 无 Jeans 叶，用 Pants
    "dress": ["dress", "dresses", "gown"],
    "skirt": ["skirt", "skirts"],
    "pants": ["pants", "trousers", "leggings"],
    "shorts": ["shorts"],
    "shirt": ["shirt", "shirts", "blouse", "tee", "t-shirt"],
    "socks": ["socks", "sock", "hosiery"],
    "jacket": ["jacket", "coat", "outerwear"],
    "sweater": ["sweater", "hoodie", "cardigan"],
    "shoes": ["shoes", "sneakers", "boots", "sandals"],
    "bag": ["handbag", "backpack", "tote", "purse"],
}

# 强品类 → 可靠 GPC 直达（taxonomy 缺叶或易被部件词带偏时）
_PRODUCT_TYPE_GPC_ALIAS = {
    "jeans": {
        "gpc_code": "204",
        "gpc_path": "Apparel & Accessories > Clothing > Pants",
        "confidence": 0.96,
        "source": "product_type_alias",
    },
    "dress": {
        "gpc_code": "2271",
        "gpc_path": "Apparel & Accessories > Clothing > Dresses",
        "confidence": 0.96,
        "source": "product_type_alias",
    },
    "socks": {
        "gpc_code": "209",
        "gpc_path": "Apparel & Accessories > Clothing > Underwear & Socks > Socks",
        "confidence": 0.96,
        "source": "product_type_alias",
    },
    "pants": {
        "gpc_code": "204",
        "gpc_path": "Apparel & Accessories > Clothing > Pants",
        "confidence": 0.94,
        "source": "product_type_alias",
    },
}

# 服饰部件/修饰词：有强品类词时不当作品类关键词
_FEATURE_NOISE = {
    "zipper", "zippered", "zip", "button", "buttons", "lace", "tied", "tie",
    "high", "waisted", "waist", "leg", "legs", "sleeve", "sleeveless",
    "printed", "print", "solid", "plain", "casual", "sexy", "slim",
    "loose", "tight", "stretch", "elastic", "women", "woman", "men", "man",
    "for", "with", "and", "the", "low", "cut", "boat", "ankle", "crew",
}


def _detect_product_types(title: str) -> list[str]:
    """从标题检测强品类词（英文）。"""
    t = (title or "").lower()
    found = []
    for canon, variants in _PRODUCT_TYPE_WORDS.items():
        if any(re.search(rf"(?<![a-z]){re.escape(v)}(?![a-z])", t) for v in variants):
            found.append(canon)
    return found


def _extract_keywords(title: str, category: str, material: str) -> list[str]:
    """从商品信息中提取英文关键词

    策略：
    1. 从中文品类映射表获取核心品类词（最高优先级）
    2. 强品类词（jeans/dress/socks）置顶并加权
    3. 从原始分类中提取（按分隔符拆分）
    4. 从标题中提取名词性词组（过滤材质/部件噪声）
    5. 材质单独处理（低权重）
    """
    keywords = []
    product_types = _detect_product_types(title)

    # 0. 中文品类映射（最高优先级，核心品类词）
    for cn_kw, mapping in CATEGORY_KEYWORD_MAP.items():
        if cn_kw in title or cn_kw in category:
            keywords.extend(mapping["keys"][:2])

    # 0b. 英文强品类词置顶（jeans 压过 zipper）
    for pt in product_types:
        keys = _PRODUCT_TYPE_WORDS.get(pt, [pt])
        # 重复注入提高相对 zipper 的得分
        keywords.extend(keys[:2] * 3)

    # 1. 从原始分类提取（只取具体品类名，跳过顶层通用词）
    generic_cats = {"apparel", "accessories", "clothing", "shoes", "home", "garden",
                    "kitchen", "dining", "food", "beverages", "sporting", "goods"}
    if category:
        cat_parts = re.split(r'[>/\-\s,]+', category)
        for part in cat_parts:
            part = part.strip().lower()
            if part and part not in generic_cats and part not in ("", "&", "and") \
               and not part.isdigit() and len(part) >= 2:
                keywords.append(part)

    # 2. 从标题提取（过滤材质/形容词/停用词/部件噪声）
    title_parts = re.split(r'[,\s，]+', title)
    skip_words = {"2024", "2025", "2026", "new", "hot", "free", "sale", "cheap", "🔥",
                  "men's", "women's", "unisex", "no.", "no", "1", "2", "3",
                  "neck", "crew", "sleeve", "fit", "style", "design", "pattern"}
    for part in title_parts:
        part = part.strip().lower()
        if len(part) < 3:
            continue
        if part in skip_words or part.isdigit():
            continue
        if part in _MATERIAL_WORDS:
            continue
        # 有强品类时跳过 zipper/tied 等部件词
        if product_types and part in _FEATURE_NOISE:
            continue
        keywords.append(part)
        if len(keywords) >= 18:
            break

    # 3. 材质单独添加（放在最后，权重最低）
    if material and material not in ("", "N/A"):
        mat_lower = material.lower()
        if mat_lower not in _MATERIAL_WORDS:
            keywords.append(mat_lower)

    # 去重，保留顺序
    seen = set()
    unique = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            unique.append(kw)

    return unique[:15]


def _rerank_candidates(title: str, candidates: list[dict]) -> list[dict]:
    """标题含服饰强信号时，优先 Apparel；压制 Arts&Crafts Zippers 误伤。"""
    if not candidates:
        return candidates
    product_types = _detect_product_types(title)
    if not product_types:
        return candidates

    def score_boost(c: dict) -> float:
        path = (c.get("gpc_path") or "").lower()
        base = float(c.get("confidence") or c.get("score") or 0)
        if path.startswith("apparel & accessories"):
            # jeans → prefer Jeans/Pants leaf
            if "jeans" in product_types and "jean" in path:
                return base + 5.0
            if "dress" in product_types and "dress" in path:
                return base + 5.0
            if "socks" in product_types and "sock" in path:
                return base + 5.0
            return base + 2.0
        # craft zippers / stationery when title is clearly clothing
        if "arts & crafts" in path or "craft fasteners" in path or "zippers" == path.split(">")[-1].strip():
            return base - 5.0
        return base

    return sorted(candidates, key=score_boost, reverse=True)


# ─────────────────────────────────────────────
# 核心匹配接口
# ─────────────────────────────────────────────

def match(title: str, category: str = "", material: str = "",
          attributes: dict = None) -> dict:
    """匹配 GPC 类目（方案C：关键词 + LLM 兜底）

    Args:
        title: 商品标题
        category: 原始分类
        material: 材质
        attributes: 额外属性

    Returns:
        {
            "gpc_code": "212",
            "gpc_path": "Apparel & Accessories > Clothing > Shirts & Tops",
            "confidence": 0.85,
            "source": "keyword",  # 或 "llm_confirm" / "llm_classify"
            "candidates": [...]   # Top 5 候选列表
        }
    """
    # 提取关键词
    keywords = _extract_keywords(title, category, material)

    # 强品类直达：jeans/dress/socks 避免 zipper 等部件词劫持
    product_types = _detect_product_types(title)
    for pt in product_types:
        alias = _PRODUCT_TYPE_GPC_ALIAS.get(pt)
        if alias:
            return {
                "gpc_code": alias["gpc_code"],
                "gpc_path": alias["gpc_path"],
                "confidence": alias["confidence"],
                "source": alias["source"],
                "candidates": [alias],
            }

    if not keywords:
        return {
            "gpc_code": "", "gpc_path": "",
            "confidence": 0.0, "source": "no_keywords",
            "candidates": [],
        }

    # 在 SQLite 中搜索候选
    candidates_raw = gpc_db.search_candidates(keywords, top_k=10)

    if not candidates_raw:
        # 无匹配 → LLM 直接分类
        return _llm_classify(title, category, material)

    # 归一化置信度（基于得分分布）
    max_score = candidates_raw[0]["score"] if candidates_raw else 1.0
    candidates = []
    for c in candidates_raw[:5]:
        confidence = min(0.99, c["score"] / max(max_score, 1.0))
        candidates.append({
            "gpc_code": c["gpc_code"],
            "gpc_path": c["gpc_path"],
            "confidence": round(confidence, 4),
            "score": c["score"],
        })

    candidates = _rerank_candidates(title, candidates)
    best = candidates[0]
    confidence = best["confidence"]
    # 服饰强信号 + Apparel 路径：抬升置信度，避免再被 LLM/部件词带偏
    if _detect_product_types(title) and (best.get("gpc_path") or "").startswith("Apparel"):
        confidence = max(confidence, 0.92)

    # 高置信度 → 直接返回
    if confidence >= GPC_CONFIDENCE_THRESHOLD:
        return {
            "gpc_code": best["gpc_code"],
            "gpc_path": best["gpc_path"],
            "confidence": round(confidence, 4),
            "source": "keyword",
            "candidates": candidates,
        }

    # 低置信度 → LLM 从候选中确认
    result = _llm_confirm_candidates(title, category, material, candidates)
    result["source"] = "llm_confirm"
    result["candidates"] = candidates
    return result


def match_batch(products: list[dict], top_k: int = 3) -> list[dict]:
    """批量匹配 GPC 类目

    高置信度直接返回，低置信度逐个调 LLM 确认。
    """
    results = []
    need_llm = []  # (index, title, category, material, candidates)

    # 第一轮：关键词匹配
    for i, p in enumerate(products):
        title = p.get("title", "")
        category = p.get("category", "")
        material = p.get("material", "")

        keywords = _extract_keywords(title, category, material)
        if not keywords:
            results.append((i, {
                "gpc_code": "", "gpc_path": "",
                "confidence": 0.0, "source": "no_keywords",
                "candidates": [],
            }))
            continue

        candidates_raw = gpc_db.search_candidates(keywords, top_k=5)
        if not candidates_raw:
            need_llm.append((i, title, category, material, []))
            continue

        max_score = candidates_raw[0]["score"]
        candidates = []
        for c in candidates_raw[:top_k]:
            conf = min(0.99, c["score"] / max(max_score, 1.0))
            candidates.append({
                "gpc_code": c["gpc_code"],
                "gpc_path": c["gpc_path"],
                "confidence": round(conf, 4),
            })

        best = candidates[0]
        if best["confidence"] >= GPC_CONFIDENCE_THRESHOLD:
            results.append((i, {
                "gpc_code": best["gpc_code"],
                "gpc_path": best["gpc_path"],
                "confidence": round(best["confidence"], 4),
                "source": "keyword",
                "candidates": candidates,
            }))
        else:
            need_llm.append((i, title, category, material, candidates))

    # 第二轮：LLM 兜底（逐个确认）
    for idx, title, category, material, candidates in need_llm:
        if candidates:
            result = _llm_confirm_candidates(title, category, material, candidates)
            result["source"] = "llm_confirm"
            result["candidates"] = candidates
        else:
            result = _llm_classify(title, category, material)
        results.append((idx, result))

    # 按原始顺序排序
    results.sort(key=lambda x: x[0])
    return [r for _, r in results]


# ─────────────────────────────────────────────
# LLM 分类（仅兜底）
# ─────────────────────────────────────────────

def _llm_classify(title: str, category: str, material: str) -> dict:
    """关键词匹配完全失败时，用 LLM 从顶层类目中分类"""
    try:
        from openai import OpenAI
    except ImportError:
        return {"gpc_code": "", "gpc_path": "", "confidence": 0.0,
                "source": "llm_unavailable", "candidates": []}

    if not DASHSCOPE_API_KEY:
        return {"gpc_code": "", "gpc_path": "", "confidence": 0.0,
                "source": "no_api_key", "candidates": []}

    # 获取顶层类目（depth ≤ 2）
    top_entries = gpc_db.get_top_level()
    cats_text = "\n".join(f"- {e['gpc_code']}: {e['gpc_path']}" for e in top_entries)

    prompt = f"""You are a Google Product Category classifier.
From the following top-level categories, pick the SINGLE most appropriate GPC code for this product.

Product:
- Title: {title}
- Source Category: {category}
- Material: {material}

Top-level Categories:
{cats_text}

Output ONLY the GPC code number. Example: 166"""

    try:
        client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10, temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()

        # 查找匹配的条目
        entry = gpc_db.get_by_code(answer)
        if entry:
            return {
                "gpc_code": entry["gpc_code"],
                "gpc_path": entry["gpc_path"],
                "confidence": 0.70,
                "source": "llm_classify",
                "candidates": [],
            }

        return {"gpc_code": answer, "gpc_path": "", "confidence": 0.50,
                "source": "llm_classify", "candidates": []}
    except Exception as e:
        return {"gpc_code": "", "gpc_path": "", "confidence": 0.0,
                "source": f"llm_error:{type(e).__name__}", "candidates": []}


def _llm_confirm_candidates(title: str, category: str, material: str,
                            candidates: list[dict]) -> dict:
    """LLM 从候选中确认最佳匹配（准确率更高）"""
    # 无候选时直接返回空
    if not candidates:
        return {"gpc_code": "", "gpc_path": "", "confidence": 0.0,
                "source": "no_candidates"}

    # 无 API key 时返回关键词最佳候选
    if not DASHSCOPE_API_KEY:
        return {
            "gpc_code": candidates[0]["gpc_code"],
            "gpc_path": candidates[0]["gpc_path"],
            "confidence": candidates[0]["confidence"],
            "source": "keyword_low_confidence",
        }

    try:
        from openai import OpenAI
    except ImportError:
        return {
            "gpc_code": candidates[0]["gpc_code"],
            "gpc_path": candidates[0]["gpc_path"],
            "confidence": candidates[0]["confidence"],
            "source": "keyword_low_confidence",
        }

    candidates_text = "\n".join(
        f"{i+1}. {c['gpc_code']} — {c['gpc_path']}"
        for i, c in enumerate(candidates)
    )

    prompt = f"""Pick the best Google Product Category code for this product.

Product: title="{title}", category="{category}", material="{material}"

Candidates:
{candidates_text}

Output ONLY the GPC code number. Example: 212"""

    try:
        client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=10, temperature=0.1,
        )
        answer = response.choices[0].message.content.strip()

        # 在候选中查找
        for c in candidates:
            if c["gpc_code"] == answer or c["gpc_code"] in answer:
                return {
                    "gpc_code": c["gpc_code"],
                    "gpc_path": c["gpc_path"],
                    "confidence": 0.80,
                    "source": "llm_confirm",
                }

        # 兜底：返回第一个候选
        return {
            "gpc_code": candidates[0]["gpc_code"],
            "gpc_path": candidates[0]["gpc_path"],
            "confidence": 0.60,
            "source": "llm_fallback",
        }
    except Exception:
        return {
            "gpc_code": candidates[0]["gpc_code"],
            "gpc_path": candidates[0]["gpc_path"],
            "confidence": candidates[0]["confidence"],
            "source": "llm_error_fallback",
        }


# ─────────────────────────────────────────────
# 向后兼容接口
# ─────────────────────────────────────────────

def load_taxonomy(force_rebuild: bool = False) -> tuple[list[dict], None]:
    """兼容旧接口：初始化 taxonomy 数据库"""
    gpc_db.init_gpc_db(force_rebuild=force_rebuild)
    return [], None
