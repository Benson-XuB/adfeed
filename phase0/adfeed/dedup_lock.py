"""AdFeed AI — MD5 哈希去重锁：防止重复上传浪费 LLM 算力

策略：
- 上传 Excel 时计算文件内容 MD5
- 查找是否已处理过相同的文件
- 若已存在 → 拒绝处理，返回上一次的结果路径
- 若不存在 → 记录并正常处理

进阶：支持"智能去重"——不是整文件 MD5，而是按行级 product_id + title + price 组合哈希，
这样用户新增一行数据时，只处理新增行，旧行跳过。
"""

import hashlib
import json
import sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional, Union

from .config import BASE_DIR

DEDUP_DB_PATH = BASE_DIR / "data" / "dedup_lock.db"


def _get_conn() -> sqlite3.Connection:
    DEDUP_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DEDUP_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_dedup (
            md5_hash        TEXT PRIMARY KEY,
            original_filename TEXT,
            file_size_bytes INTEGER,
            row_count       INTEGER,
            task_id         TEXT,
            created_at      TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS row_dedup (
            row_hash        TEXT PRIMARY KEY,
            product_id      TEXT,
            file_md5        TEXT,
            last_processed_at TEXT
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_row_dedup_product
        ON row_dedup(product_id)
    """)

    conn.commit()


# ─────────────────────────────────────────────
# 文件级去重
# ─────────────────────────────────────────────

def file_md5(file_path: Union[str, Path]) -> str:
    """计算文件 MD5 哈希"""
    hasher = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def check_file(file_path: str, force: bool = False) -> dict:
    """检查文件是否已处理过

    Returns:
        {
            "is_duplicate": bool,
            "md5": "...",
            "previous_task_id": "..." | None,
            "previous_at": "..." | None,
        }
    """
    md5 = file_md5(file_path)

    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM file_dedup WHERE md5_hash = ?", (md5,)
    ).fetchone()
    conn.close()

    if row and not force:
        return {
            "is_duplicate": True,
            "md5": md5,
            "previous_task_id": row["task_id"],
            "previous_at": row["created_at"],
            "original_filename": row["original_filename"],
        }

    return {
        "is_duplicate": False,
        "md5": md5,
        "previous_task_id": None,
        "previous_at": None,
    }


def record_file(file_path: str, task_id: str, row_count: int = 0):
    """记录文件已处理"""
    md5 = file_md5(file_path)
    file_size = Path(file_path).stat().st_size

    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO file_dedup
        (md5_hash, original_filename, file_size_bytes, row_count, task_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (md5, Path(file_path).name, file_size, row_count, task_id,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


# ─────────────────────────────────────────────
# 行级去重（product_id + title + price 组合）
# ─────────────────────────────────────────────

def row_hash(product_id: str, title: str, price: float) -> str:
    """计算单行数据哈希（product_id + title + price）"""
    content = f"{product_id}|{title.strip().lower()}|{price:.2f}"
    return hashlib.md5(content.encode("utf-8")).hexdigest()


def check_row(product_id: str, title: str, price: float) -> Optional[dict]:
    """检查单行是否已处理过

    Returns:
        None 如果未处理过，dict 如果已处理（含上次处理时间）
    """
    rh = row_hash(product_id, title, price)
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM row_dedup WHERE row_hash = ?", (rh,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None


def record_row(product_id: str, title: str, price: float, file_md5: str = ""):
    """记录单行已处理"""
    rh = row_hash(product_id, title, price)
    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO row_dedup
        (row_hash, product_id, file_md5, last_processed_at)
        VALUES (?, ?, ?, ?)
    """, (rh, product_id, file_md5,
          datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()


def dedup_rows(products: list[dict]) -> dict:
    """对产品列表做行级去重

    Returns:
        {
            "to_process": [...],     # 新行（需要 AI 处理）
            "already_processed": [...],  # 已处理行（跳过）
            "stats": {"total": N, "new": N, "duplicate": N}
        }
    """
    to_process = []
    already_processed = []

    for p in products:
        rh = row_hash(
            p.get("product_id", ""),
            p.get("title", ""),
            p.get("price_cny", p.get("price", 0)),
        )
        existing = check_row(
            p.get("product_id", ""),
            p.get("title", ""),
            p.get("price_cny", p.get("price", 0)),
        )
        if existing:
            already_processed.append({**p, "_row_hash": rh, "_last_processed": existing["last_processed_at"]})
        else:
            to_process.append({**p, "_row_hash": rh})

    return {
        "to_process": to_process,
        "already_processed": already_processed,
        "stats": {
            "total": len(products),
            "new": len(to_process),
            "duplicate": len(already_processed),
        },
    }
