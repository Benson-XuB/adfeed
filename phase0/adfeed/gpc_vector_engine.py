"""AdFeed AI — ChromaDB 向量 GPC 匹配引擎（替换关键词匹配）

使用 ChromaDB 将 Google Product Taxonomy 全量向量化。
当商品数据进入时，通过余弦相似度（Cosine Similarity）KNN 搜索匹配出
100% 绝对字符对齐的官方 GPC 编码，零 LLM Token 消耗。

支持两种 Embedding 模式：
1. LOCAL (默认): 使用 ChromaDB 内置 sentence-transformers，完全离线零 API 费
2. DASHSCOPE: 使用通义千问 text-embedding API（需 API Key）
"""

import os
import json
import time
from pathlib import Path

from .config import (
    TAXONOMY_FILE, BASE_DIR, DASHSCOPE_API_KEY, DASHSCOPE_BASE_URL,
)


CHROMA_PERSIST_DIR = str(BASE_DIR / "data" / "chroma_gpc")
COLLECTION_NAME = "gpc_taxonomy"

# ─────────────────────────────────────────────
# Taxonomy 解析（复用原有解析逻辑）
# ─────────────────────────────────────────────

def _parse_taxonomy_entries() -> list[dict]:
    """解析 Google taxonomy 文件为标准化条目列表"""
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
                    "gpc_path": path.strip(),
                    "display_text": path.strip(),
                    # 构建语义化搜索文本：拆分层级，展开缩写
                    "search_text": _build_search_text(path.strip()),
                })
    return entries


def _build_search_text(gpc_path: str) -> str:
    """从 GPC 路径构建语义化搜索文本

    将 "Apparel & Accessories > Clothing > Dresses" 
    展开为 "Apparel Accessories Clothing Dresses clothing dress"
    提高向量语义匹配精度。
    """
    parts = [p.strip() for p in gpc_path.split(">")]
    # 添加到末尾的单数形式变体
    expanded = list(parts)
    for part in parts:
        words = part.lower().split()
        for w in words:
            # 去复数化
            if w.endswith("ies"):
                expanded.append(w[:-3] + "y")
            elif w.endswith("ses"):
                expanded.append(w[:-2])
            elif w.endswith("s") and not w.endswith("ss"):
                expanded.append(w[:-1])
    return " ".join(expanded)


# ─────────────────────────────────────────────
# ChromaDB 管理
# ─────────────────────────────────────────────

_gpc_collection = None  # chromadb.Collection (lazy import)
_entries_map: dict[str, dict] = {}  # doc_id → entry


def _get_embedding_function():
    """获取 Embedding 函数

    优先使用本地 sentence-transformers（零 API 费），
    若不可用则回退到 DashScope API。
    """
    use_local = os.getenv("GPC_EMBEDDING_MODE", "local") == "local"

    if use_local:
        try:
            from chromadb.utils import embedding_functions
            return embedding_functions.DefaultEmbeddingFunction()
        except ImportError:
            pass

    # DashScope text-embedding API 兜底
    if DASHSCOPE_API_KEY:
        try:
            from chromadb.utils import embedding_functions
            class DashScopeEmbedding(embedding_functions.EmbeddingFunction):
                def __init__(self):
                    from openai import OpenAI
                    self._client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

                def __call__(self, input):
                    texts = input if isinstance(input, list) else [input]
                    response = self._client.embeddings.create(
                        model="text-embedding-v3", input=texts,
                    )
                    return [d.embedding for d in response.data]

            return DashScopeEmbedding()
        except Exception:
            pass

    # 最终兜底：ChromaDB 默认
    try:
        from chromadb.utils import embedding_functions
        return embedding_functions.DefaultEmbeddingFunction()
    except ImportError:
        raise RuntimeError(
            "ChromaDB embedding function unavailable. "
            "Install: pip install chromadb sentence-transformers"
        )


def init_engine(force_rebuild: bool = False):
    """初始化 ChromaDB 向量引擎（首次自动建库）"""
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    global _gpc_collection, _entries_map

    if _gpc_collection is not None and not force_rebuild:
        return _gpc_collection

    Path(CHROMA_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=CHROMA_PERSIST_DIR,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    embedding_fn = _get_embedding_function()
    print(f"[GPCVector] Embedding 模式: {embedding_fn.__class__.__name__}")

    # 若 force_rebuild 则删旧库
    if force_rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
            print("[GPCVector] 已删除旧 ChromaDB 集合，将重建")
        except Exception:
            pass

    # 获取或创建集合
    try:
        _gpc_collection = client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
        existing_count = _gpc_collection.count()
        print(f"[GPCVector] ChromaDB 已存在: {existing_count} 条向量")
    except Exception:
        _gpc_collection = client.create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        print("[GPCVector] 创建新 ChromaDB 集合，开始向量化 taxonomy...")

    # 若集合为空则灌数据
    if _gpc_collection.count() == 0:
        _populate_collection(_gpc_collection)

    # 构建 entries_map
    if not _entries_map:
        entries = _parse_taxonomy_entries()
        for e in entries:
            _entries_map[e["gpc_code"]] = e

    return _gpc_collection


def _populate_collection(collection):
    """将 taxonomy 条目向量化并批量写入 ChromaDB"""
    entries = _parse_taxonomy_entries()
    total = len(entries)
    batch_size = 500

    for batch_start in range(0, total, batch_size):
        batch = entries[batch_start:batch_start + batch_size]
        ids = [f"gpc_{e['gpc_code']}" for e in batch]
        documents = [e["search_text"] for e in batch]
        metadatas = [
            {"gpc_code": e["gpc_code"], "gpc_path": e["gpc_path"]}
            for e in batch
        ]

        collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

        pct = min(100, int((batch_start + batch_size) / total * 100))
        print(f"\r[GPCVector] 向量化中... {pct}% ({batch_start + len(batch)}/{total})", end="")

    print(f"\n[GPCVector] 向量化完成！{total} 条类目已入库")
    _entries_map = {e["gpc_code"]: e for e in entries}


# ─────────────────────────────────────────────
# 核心匹配接口（与 gpc_matcher.match() 签名一致）
# ─────────────────────────────────────────────

def match(
    title: str,
    category: str = "",
    material: str = "",
    attributes: dict = None,
    top_k: int = 5,
    min_confidence: float = 0.35,
) -> dict:
    """通过向量相似度匹配 GPC 类目（零 LLM Token 消耗）

    Args:
        title: 商品原始标题
        category: 原始分类
        material: 材质
        attributes: 额外属性
        top_k: 返回候选数量
        min_confidence: 最低置信度阈值（低于则标记为 low_confidence）

    Returns:
        {
            "gpc_code": "2271",
            "gpc_path": "Apparel & Accessories > Clothing > Dresses",
            "confidence": 0.87,
            "source": "chromadb_vector",
            "candidates": [...]  # top_k 候选列表
        }
    """
    collection = init_engine()

    # 构建查询文本：组合所有可用信息
    query_parts = [title]
    if category:
        query_parts.append(category)
    if material:
        query_parts.append(material)
    if attributes:
        query_parts.append(" ".join(f"{k} {v}" for k, v in attributes.items()))

    query_text = " ".join(query_parts)

    # 向量搜索
    results = collection.query(
        query_texts=[query_text],
        n_results=top_k,
        include=["metadatas", "distances", "documents"],
    )

    if not results["ids"] or not results["ids"][0]:
        return {
            "gpc_code": "",
            "gpc_path": "",
            "confidence": 0.0,
            "source": "chromadb_no_match",
            "candidates": [],
        }

    # 处理结果
    raw_distances = results["distances"][0]  # ChromaDB cosine distance: 0(identical) ~ 2(opposite)

    candidates = []
    for i in range(len(results["ids"][0])):
        gpc_code = results["metadatas"][0][i]["gpc_code"]
        gpc_path = results["metadatas"][0][i]["gpc_path"]
        distance = raw_distances[i]

        # Cosine distance → similarity score (0~1)
        similarity = 1.0 - (distance / 2.0)

        candidates.append({
            "gpc_code": gpc_code,
            "gpc_path": gpc_path,
            "similarity": round(similarity, 4),
            "distance": round(distance, 4),
        })

    # 最佳匹配
    best = candidates[0]
    confidence = best["similarity"]

    # 若最佳匹配不够高但次优明显不同，提升置信度
    if len(candidates) >= 2:
        gap = best["similarity"] - candidates[1]["similarity"]
        if gap > 0.15:
            confidence = min(0.99, confidence + 0.1)

    source = "chromadb_vector"
    if confidence < min_confidence:
        source = "chromadb_low_confidence"

    return {
        "gpc_code": best["gpc_code"],
        "gpc_path": best["gpc_path"],
        "confidence": round(confidence, 4),
        "source": source,
        "candidates": candidates[:5],
    }


def match_batch(
    products: list[dict],
    top_k: int = 3,
) -> list[dict]:
    """批量匹配（一次向量搜索处理多条商品）"""
    collection = init_engine()

    queries = []
    for p in products:
        parts = [p.get("title", "")]
        if p.get("category"):
            parts.append(p["category"])
        if p.get("material"):
            parts.append(p["material"])
        queries.append(" ".join(parts))

    results = collection.query(
        query_texts=queries,
        n_results=top_k,
        include=["metadatas", "distances"],
    )

    output = []
    for i in range(len(queries)):
        if not results["ids"][i]:
            output.append({
                "gpc_code": "", "gpc_path": "", "confidence": 0.0,
                "source": "chromadb_no_match", "candidates": [],
            })
            continue

        candidates = []
        for j in range(len(results["ids"][i])):
            gpc_code = results["metadatas"][i][j]["gpc_code"]
            gpc_path = results["metadatas"][i][j]["gpc_path"]
            distance = results["distances"][i][j]
            similarity = 1.0 - (distance / 2.0)
            candidates.append({
                "gpc_code": gpc_code,
                "gpc_path": gpc_path,
                "similarity": round(similarity, 4),
            })

        best = candidates[0]
        output.append({
            "gpc_code": best["gpc_code"],
            "gpc_path": best["gpc_path"],
            "confidence": round(best["similarity"], 4),
            "source": "chromadb_vector",
            "candidates": candidates[:top_k],
        })

    return output


def get_stats() -> dict:
    """获取向量引擎统计信息"""
    collection = init_engine()
    return {
        "total_entries": collection.count(),
        "collection_name": COLLECTION_NAME,
        "persist_dir": CHROMA_PERSIST_DIR,
    }


# ─────────────────────────────────────────────
# 向后兼容：保持与 gpc_matcher 相同的 load_taxonomy() 签名
# ─────────────────────────────────────────────

def load_taxonomy(force_rebuild: bool = False) -> tuple:
    """兼容旧接口：加载 taxonomy 并初始化向量引擎"""
    collection = init_engine(force_rebuild=force_rebuild)
    return _parse_taxonomy_entries(), collection
