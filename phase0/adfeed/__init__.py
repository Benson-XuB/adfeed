"""
AdFeed AI — 跨境广告数据洗白引擎 v2

模块：
    gpc_vector_engine  — ChromaDB 向量 GPC 匹配（零 LLM Token）
    title_optimizer    — AI 标题优化（品类化公式 + Structured Outputs + 70字符加载）
    compliance_engine  — 违禁词正则防火墙（四层规则）
    product_memory     — PRODUCT_MEMORY_DB 增量同步（老商品零 Token）
    dedup_lock         — MD5 哈希去重锁（防重复上传）
    cultural_context   — 海外文化场景字典外挂
    feed_generator     — Feed XML 生成器（动态路由 + inventory 熔断）
    pipeline           — 核心编排器
    mock_data          — 模拟数据生成器
"""

__version__ = "0.2.0"


def get_memory_stats():
    from .product_memory import get_stats
    return get_stats()


def get_gpc_stats():
    from .gpc_vector_engine import get_stats
    return get_stats()

