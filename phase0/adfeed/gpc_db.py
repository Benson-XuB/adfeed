"""AdFeed AI — GPC Taxonomy SQLite 存储层（方案C：关键词 + LLM 兜底）

将 Google 官方 5596 条分类（含数字 ID）同步到本地 SQLite 数据库。
替代 ChromaDB embedding 方案，零外部依赖，查询更快更准。

用法：
    from .gpc_db import init_gpc_db, search_candidates
    init_gpc_db()  # 首次自动导入 taxonomy
    candidates = search_candidates(["t-shirt", "shirt", "cotton"])
"""

import re
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

from .config import TAXONOMY_FILE, DATA_DIR

GPC_DB_PATH = DATA_DIR / "gpc_taxonomy.db"


# ─────────────────────────────────────────────
# 数据库连接
# ─────────────────────────────────────────────

@contextmanager
def _conn():
    """SQLite 连接上下文管理器（WAL 模式，外键开启）"""
    c = sqlite3.connect(str(GPC_DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    try:
        yield c
    finally:
        c.close()


# ─────────────────────────────────────────────
# Schema
# ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS gpc_taxonomy (
    gpc_code    TEXT PRIMARY KEY,
    gpc_path    TEXT NOT NULL,           -- 完整路径 "Apparel & Accessories > Clothing > Shirts & Tops"
    depth       INTEGER NOT NULL,        -- 层级深度（1=顶层）
    parent_code TEXT,                    -- 父节点 gpc_code（顶层为 NULL）
    leaf_name   TEXT NOT NULL,           -- 最后一级名称 "Shirts & Tops"
    search_text TEXT NOT NULL            -- 搜索优化文本（去特殊字符、单复数展开）
);

CREATE INDEX IF NOT EXISTS idx_gpc_depth ON gpc_taxonomy(depth);
CREATE INDEX IF NOT EXISTS idx_gpc_parent ON gpc_taxonomy(parent_code);
CREATE INDEX IF NOT EXISTS idx_gpc_leaf ON gpc_taxonomy(leaf_name);
"""


def init_gpc_db(force_rebuild: bool = False) -> int:
    """初始化 GPC taxonomy 数据库

    首次调用自动从 taxonomy 文件导入。
    返回导入条目数。

    Args:
        force_rebuild: 强制重建（删除旧表重新导入）

    Returns:
        int: taxonomy 条目总数
    """
    with _conn() as c:
        c.executescript(SCHEMA)
        c.commit()

        # 检查是否已有数据
        count = c.execute("SELECT COUNT(*) FROM gpc_taxonomy").fetchone()[0]
        if count > 0 and not force_rebuild:
            return count

        # 清空旧数据（force_rebuild 场景）
        if force_rebuild:
            c.execute("DELETE FROM gpc_taxonomy")
            c.commit()

        # 解析 taxonomy 文件
        entries = _parse_taxonomy_file()

        # 批量写入
        c.executemany(
            """INSERT OR REPLACE INTO gpc_taxonomy
               (gpc_code, gpc_path, depth, parent_code, leaf_name, search_text)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [(e["gpc_code"], e["gpc_path"], e["depth"],
              e["parent_code"], e["leaf_name"], e["search_text"])
             for e in entries],
        )
        c.commit()

        total = c.execute("SELECT COUNT(*) FROM gpc_taxonomy").fetchone()[0]
        print(f"[GPC DB] 导入完成：{total} 条分类已入库")
        return total


# ─────────────────────────────────────────────
# Taxonomy 文件解析
# ─────────────────────────────────────────────

def _parse_taxonomy_file() -> list[dict]:
    """解析 Google taxonomy 文本文件

    格式：`ID - Path > Subpath > Leaf`
    示例：`1604 - Apparel & Accessories > Clothing > Shirts & Tops`

    Returns:
        list[dict]: 包含 gpc_code, gpc_path, depth, parent_code, leaf_name, search_text
    """
    entries = []
    path_to_code = {}  # 路径 → gpc_code 映射（用于查找 parent_code）

    with open(TAXONOMY_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            parts = line.split(" - ", 1)
            if len(parts) != 2:
                continue

            gpc_code = parts[0].strip()
            gpc_path = parts[1].strip()

            # 计算层级深度
            segments = [s.strip() for s in gpc_path.split(">")]
            depth = len(segments)
            leaf_name = segments[-1]

            # 查找 parent_code
            parent_code = None
            if depth > 1:
                parent_path = " > ".join(segments[:-1])
                parent_code = path_to_code.get(parent_path)

            # 记录当前路径到 code 映射
            path_to_code[gpc_path] = gpc_code

            # 构建搜索优化文本
            search_text = _build_search_text(gpc_path)

            entries.append({
                "gpc_code": gpc_code,
                "gpc_path": gpc_path,
                "depth": depth,
                "parent_code": parent_code,
                "leaf_name": leaf_name,
                "search_text": search_text,
            })

    return entries


def _build_search_text(gpc_path: str) -> str:
    """从 GPC 路径构建搜索优化文本

    将 "Apparel & Accessories > Clothing > Dresses"
    展开为 "apparel accessories clothing dresses dress"
    提高关键词匹配命中率。
    """
    parts = [p.strip() for p in gpc_path.split(">")]
    expanded = list(parts)

    for part in parts:
        words = part.lower().split()
        for w in words:
            # 去复数化（简单规则）
            if w.endswith("ies"):
                expanded.append(w[:-3] + "y")
            elif w.endswith("ses") or w.endswith("xes"):
                expanded.append(w[:-2])
            elif w.endswith("s") and not w.endswith("ss") and len(w) > 2:
                expanded.append(w[:-1])

    # 去特殊字符，转小写
    text = " ".join(expanded).lower()
    for ch in "&/'()-":
        text = text.replace(ch, " ")
    return " ".join(text.split())  # 去多余空格


# ─────────────────────────────────────────────
# 查询接口
# ─────────────────────────────────────────────

def search_candidates(keywords: list[str], top_k: int = 10,
                      max_depth: int = 0) -> list[dict]:
    """根据关键词搜索候选 GPC 分类

    使用 SQLite LIKE 查询，对 search_text 和 gpc_path 进行模糊匹配。
    每个关键词命中加分，越深的层级权重越高。

    Args:
        keywords: 搜索关键词列表（英文，已小写化）
        top_k: 返回候选数量
        max_depth: 限制最大深度（0=不限）

    Returns:
        list[dict]: 按得分排序的候选列表
            [{"gpc_code": "1604", "gpc_path": "...", "score": 5.2, "depth": 3}, ...]
    """
    if not keywords:
        return []

    with _conn() as c:
        # 构建 SQL：每个关键词生成一个 LIKE 条件
        # 短关键词（≤4字符）使用词边界匹配，避免子串假阳性
        # 连字符关键词（如 "t-shirt"）拆分为子词分别搜索
        conditions = []
        params = []
        expanded_keywords = []
        for kw in keywords:
            kw_clean = kw.strip().lower()
            if not kw_clean or len(kw_clean) < 2:
                continue
            expanded_keywords.append(kw_clean)
            # 拆分连字符词（如 "t-shirt" → ["t", "shirt"]）
            if '-' in kw_clean:
                for sub in kw_clean.split('-'):
                    if len(sub) >= 3 and sub != kw_clean:
                        expanded_keywords.append(sub)

        for kw_clean in expanded_keywords:
            if len(kw_clean) <= 4:
                # 短词：词边界匹配
                conditions.append("((' ' || search_text || ' ') LIKE ? OR (' ' || gpc_path || ' ') LIKE ?)")
                params.extend([f"% {kw_clean} %", f"% {kw_clean} %"])
            else:
                conditions.append("(search_text LIKE ? OR gpc_path LIKE ?)")
                params.extend([f"%{kw_clean}%", f"%{kw_clean}%"])

        if not conditions:
            return []

        where = " OR ".join(conditions)
        depth_filter = "AND depth <= ?" if max_depth > 0 else ""
        if max_depth > 0:
            params.append(max_depth)

        sql = f"""
            SELECT gpc_code, gpc_path, depth, parent_code, leaf_name, search_text
            FROM gpc_taxonomy
            WHERE {where} {depth_filter}
        """

        rows = c.execute(sql, params).fetchall()

        # 计算得分
        scored = []
        for row in rows:
            score = _score_entry(row, keywords)
            if score > 0:
                scored.append({
                    "gpc_code": row["gpc_code"],
                    "gpc_path": row["gpc_path"],
                    "depth": row["depth"],
                    "parent_code": row["parent_code"],
                    "leaf_name": row["leaf_name"],
                    "score": score,
                })

        # 按得分降序排列，取 top_k
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]


def _score_entry(row: sqlite3.Row, keywords: list[str]) -> float:
    """计算一个 taxonomy 条目对关键词的匹配得分

    评分策略：
    - 叶子节点精确匹配：最高权重
    - 单词级匹配（分词后匹配）：处理 "t-shirt" → "shirts" 等情况
    - 路径中包含关键词：中等权重
    - 深度惩罚：过深路径轻微降权
    """
    score = 0.0
    search_text = row["search_text"].lower()
    gpc_path = row["gpc_path"].lower()
    leaf_name = row["leaf_name"].lower()
    depth = row["depth"]

    leaf_hits = 0
    path_hits = 0

    # 预计算叶子节点分词（用于单词级匹配）
    leaf_tokens = set()
    for word in re.split(r'[\s&\-/]+', leaf_name):
        word = word.strip()
        if len(word) >= 3:
            leaf_tokens.add(word)
            # 单数/复数变体
            if word.endswith("s") and len(word) > 3:
                leaf_tokens.add(word[:-1])
            elif word.endswith("ies"):
                leaf_tokens.add(word[:-3] + "y")

    for kw in keywords:
        kw = kw.strip().lower()
        if not kw or len(kw) < 2:
            continue

        # 词边界检查：关键词须为完整词，避免 short→shorts、men→treatment
        is_substring_match = False
        if kw in leaf_name:
            pattern = r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])'
            is_substring_match = not bool(re.search(pattern, leaf_name))
            if not is_substring_match:
                leaf_hits += 1
                score += 4.0
                if leaf_name == kw or leaf_name == kw + "s" or leaf_name == kw + "es":
                    score += 3.0
            elif leaf_name == kw + "s" or leaf_name == kw + "es":
                # 合法复数（sock→socks），但排除形容词假复数已由词边界挡住 short→shorts
                # short + s == shorts 且 short 不是 shorts 的整词 → 上面 is_substring_match=True
                # 仅当 kw 本身已是叶子词干的规范单数时加分：要求 kw 长度>=4 且不是严格短前缀误伤
                # 此处不再给「纯前缀+s」加分（short/shorts 已在 is_substring_match 分支）
                pass
        else:
            # 单词级匹配：分词后检查叶子节点
            kw_tokens = [t.strip() for t in re.split(r'[\s\-/]+', kw) if len(t.strip()) >= 3]
            word_match = False
            for kt in kw_tokens:
                if kt in leaf_tokens:
                    word_match = True
                    break
                if kt.endswith("s") and kt[:-1] in leaf_tokens:
                    word_match = True
                    break
                if kt + "s" in leaf_tokens:
                    word_match = True
                    break

            if word_match:
                leaf_hits += 1
                score += 3.5  # 单词级叶子匹配
            elif kw in gpc_path:
                # 路径中包含关键词（父级分类名匹配）
                # 短词需要词边界检查
                if len(kw) <= 4:
                    pattern = r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])'
                    if not re.search(pattern, gpc_path):
                        continue  # 假阳性，跳过
                path_segments = [s.strip() for s in gpc_path.split(">")]
                if any(kw in seg for seg in path_segments[:-1]):
                    path_hits += 1
                    score += 1.5
                else:
                    path_hits += 1
                    score += 0.3
            elif kw in search_text:
                # 搜索文本中包含（短词需要词边界检查）
                if len(kw) <= 4:
                    pattern = r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])'
                    if not re.search(pattern, search_text):
                        continue  # 假阳性，跳过
                path_hits += 1
                score += 0.2

    # 叶子命中奖励
    if leaf_hits >= 2:
        score *= 1.2

    # 纯路径命中惩罚
    if leaf_hits == 0 and path_hits >= 3:
        score *= 0.6

    # 深度惩罚
    if depth > 4:
        score *= max(0.5, 1.0 - (depth - 4) * 0.1)

    return round(score, 4)


def get_by_code(gpc_code: str) -> Optional[dict]:
    """根据 GPC code 获取分类详情"""
    with _conn() as c:
        row = c.execute(
            "SELECT gpc_code, gpc_path, depth, parent_code, leaf_name FROM gpc_taxonomy WHERE gpc_code = ?",
            (gpc_code,),
        ).fetchone()

    if not row:
        return None

    return {
        "gpc_code": row["gpc_code"],
        "gpc_path": row["gpc_path"],
        "depth": row["depth"],
        "parent_code": row["parent_code"],
        "leaf_name": row["leaf_name"],
    }


def get_children(parent_code: str) -> list[dict]:
    """获取某分类的所有子分类"""
    with _conn() as c:
        rows = c.execute(
            """SELECT gpc_code, gpc_path, depth, leaf_name
               FROM gpc_taxonomy WHERE parent_code = ?
               ORDER BY gpc_path""",
            (parent_code,),
        ).fetchall()

    return [
        {"gpc_code": r["gpc_code"], "gpc_path": r["gpc_path"],
         "depth": r["depth"], "leaf_name": r["leaf_name"]}
        for r in rows
    ]


def get_top_level() -> list[dict]:
    """获取顶层分类（depth=1）"""
    with _conn() as c:
        rows = c.execute(
            """SELECT gpc_code, gpc_path, leaf_name
               FROM gpc_taxonomy WHERE depth = 1
               ORDER BY gpc_path""",
        ).fetchall()

    return [
        {"gpc_code": r["gpc_code"], "gpc_path": r["gpc_path"], "leaf_name": r["leaf_name"]}
        for r in rows
    ]


def get_stats() -> dict:
    """获取 taxonomy 统计信息"""
    with _conn() as c:
        total = c.execute("SELECT COUNT(*) FROM gpc_taxonomy").fetchone()[0]
        max_depth = c.execute("SELECT MAX(depth) FROM gpc_taxonomy").fetchone()[0]
        top_level = c.execute("SELECT COUNT(*) FROM gpc_taxonomy WHERE depth = 1").fetchone()[0]

    return {
        "total_entries": total,
        "max_depth": max_depth,
        "top_level_categories": top_level,
        "db_path": str(GPC_DB_PATH),
    }


# ─────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────

# 模块加载时自动初始化（如果 DB 文件不存在）
if not GPC_DB_PATH.exists():
    init_gpc_db()
