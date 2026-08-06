"""AdFeed AI — 1688/速卖通/手工表脏词清洗引擎 v1.0

绝对切除中文电商平台污染词汇，确保输出到 Google Shopping 的标题和描述干净专业。
覆盖：1688、速卖通(AliExpress)、店小秘ERP、微信手工表等常见数据源的脏词。
"""

import re
from typing import List

# ═══════════════════════════════════════════════════════════════
# 脏词词典 — 按来源分类，统一清洗
# ═══════════════════════════════════════════════════════════════

# 英文脏词（1688跨境、AliExpress、Alibaba常用）
DIRTY_WORDS_EN: list[str] = [
    # 1688 / Alibaba 跨境污染词
    r'\b1688\b', r'\balibaba\b', r'\balibaba\.com\b', r'\baliexpress\b',
    r'\bali express\b', r'\btaobao\b', r'\btmall\b', r'\bmade in china\b',
    # 跨境营销废话
    r'\bhot sale\b', r'\bhot selling\b', r'\bcross[- ]border\b',
    r'\bexplosive(?:ly)?\b', r'\bfactory direct\b', r'\bnew arrival[s]?\b',
    r'\bwholesale\b', r'\bwholesale price\b', r'\bfree shipping\b',
    r'\bdrop ?shipping\b', r'\bOEM(?: order)?\b', r'\bODM\b',
    r'\bcustom(?:ized)? order\b', r'\bsample available\b',
    r'\bhigh quality\b', r'\bbest quality\b', r'\btop quality\b',
    r'\bpremium quality\b', r'\bhigh[- ]end\b',
    r'\bcompetitive price\b', r'\bfactory price\b', r'\bcheap(?:est)?\b',
    r'\blow(?:est)? price\b', r'\bdirect(?:ly)? from factory\b',
    r'\bmanufacturer(?:s)?\b', r'\bsupplier(?:s)?\b',
    # 年份废话词
    r'\b202[0-9]\s*(?:new|newest|latest|upgraded)\b',
    r'\bnew (?:202[0-9]|version|model|design|style)\b',
    # 电商废话填充
    r'\b(?:in )?stock\b', r'\bready to ship\b', r'\bfast delivery\b',
    r'\bquick ship\b', r'\bsame day ship\b', r'\bfast shipping\b',
    r'\bmoq\b', r'\bmin(?:imum)? order\b',
    r'\bhigh[- ]?sales\b', r'\bbest[- ]?seller\b', r'\btop[- ]?selling\b',
    r'\btrending\b', r'\bviral\b', r'\bmust[- ]?have\b',
    # 平台引流词
    r'\bamazon(?:\.com)?\b', r'\bebay\b', r'\bwish\.com\b', r'\btemu\b',
    r'\bshein\b',
]

# 中文脏词（1688后台、店小秘、微信手工表）
DIRTY_WORDS_CN: list[str] = [
    # 1688 / 阿里系
    r'1688', r'阿里巴巴', r'速卖通', r'淘宝', r'天猫', r'拼多多',
    # 跨境营销废话
    r'跨境', r'外贸', r'出口', r'内销', r'外销',
    r'厂家直销', r'工厂直发', r'源头工厂', r'实力厂家',
    r'一件代发', r'代发', r'代理', r'分销', r'批发', r'混批',
    r'支持定制', r'来图定制', r'来样定制', r'OEM', r'ODM',
    r'免费拿样', r'样品 available',
    # 质量废话
    r'爆款', r'热卖', r'火爆', r'疯抢', r'疯卖', r'大卖',
    r'高品质', r'优质', r'高端', r'精品', r'精品品质',
    r'质量保证', r'品质保证', r'质量可靠',
    r'低价', r'最低价', r'全网最低', r'便宜', r'实惠',
    r'性价比', r'性价比高',
    # 物流废话
    r'现货', r'秒发', r'当天发', r'24小时发', r'闪电发货',
    r'包邮', r'顺丰包邮', r'快递包邮',
    # 年份废话
    r'(?:202[0-9]年?)?(?:新款|新品|新款式|升级版|改良版)',
    r'新款上市', r'秋季新款', r'春季新款', r'夏季新款', r'冬季新款',
    # 电商引流词
    r'抖音同款', r'网红同款', r'明星同款', r'ins同款',
    r'小红书推荐', r'直播爆款',
    # 规格废话
    r'均码', r'自由码', r'通用款',
]

# 编译正则（忽略大小写）
_DIRTY_EN_PATTERNS: list[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in DIRTY_WORDS_EN
]
_DIRTY_CN_PATTERNS: list[re.Pattern] = [
    re.compile(p) for p in DIRTY_WORDS_CN
]


def clean_dirty_words(title: str, description: str = "") -> dict:
    """清洗标题和描述中的脏词

    Args:
        title: 原始商品标题
        description: 原始商品描述

    Returns:
        {
            "clean_title": "清洗后的标题",
            "clean_description": "清洗后的描述",
            "removed_words": ["hot sale", "factory direct", ...],
            "dirty_count": 3  # 移除的脏词数量
        }
    """
    removed: list[str] = []

    clean_title = _clean_text(title, removed)
    clean_desc = _clean_text(description, removed) if description else ""

    # 去重
    seen = set()
    unique_removed = []
    for w in removed:
        w_lower = w.lower()
        if w_lower not in seen:
            seen.add(w_lower)
            unique_removed.append(w)

    return {
        "clean_title": clean_title,
        "clean_description": clean_desc,
        "removed_words": unique_removed,
        "dirty_count": len(unique_removed),
    }


def _clean_text(text: str, removed_collector: list[str]) -> str:
    """清洗单段文本，将匹配的脏词记录到 removed_collector"""
    if not text:
        return text

    # 先处理英文脏词
    for pattern in _DIRTY_EN_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            removed_collector.append(m.strip())
        text = pattern.sub("", text)

    # 再处理中文脏词
    for pattern in _DIRTY_CN_PATTERNS:
        matches = pattern.findall(text)
        for m in matches:
            removed_collector.append(m.strip())
        text = pattern.sub("", text)

    # 清理残留的多余空格和标点
    text = re.sub(r'\s{2,}', ' ', text)
    text = re.sub(r'[,，;；]\s*[,，;；]', ',', text)  # 合并连续标点
    text = re.sub(r'^[\s,，.。;；:：\-—]+', '', text)  # 去开头标点
    text = re.sub(r'[\s,，.。;；:：\-—]+$', '', text)  # 去结尾标点
    text = text.strip()

    return text


def is_dirty(text: str) -> bool:
    """快速检测文本是否含有脏词（不执行清洗）"""
    if not text:
        return False
    text_lower = text.lower()
    for pattern in _DIRTY_EN_PATTERNS:
        if pattern.search(text_lower):
            return True
    for pattern in _DIRTY_CN_PATTERNS:
        if pattern.search(text):
            return True
    return False


def get_dirty_report(title: str, description: str = "") -> dict:
    """生成脏词检测报告（只读，不修改原文）

    Returns:
        {
            "is_dirty": True/False,
            "title_dirty_words": ["hot sale", "爆款"],
            "desc_dirty_words": ["factory direct"],
            "total_count": 3
        }
    """
    title_words = []
    desc_words = []

    if title:
        for pattern in _DIRTY_EN_PATTERNS + _DIRTY_CN_PATTERNS:
            matches = pattern.findall(title)
            title_words.extend(m.strip() for m in matches)

    if description:
        for pattern in _DIRTY_EN_PATTERNS + _DIRTY_CN_PATTERNS:
            matches = pattern.findall(description)
            desc_words.extend(m.strip() for m in matches)

    total = len(title_words) + len(desc_words)
    return {
        "is_dirty": total > 0,
        "title_dirty_words": list(set(title_words)),
        "desc_dirty_words": list(set(desc_words)),
        "total_count": total,
    }
