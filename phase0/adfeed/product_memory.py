"""AdFeed AI — PRODUCT_MEMORY_DB: 增量同步与数据库状态隔离

实现"老商品零 Token 耗费"的核心逻辑：
- product_id 已存在 → 仅更新 price（换算美金）和 inventory，Token = 0
- product_id 不存在 → 标记为新品，触发 AI 全量清洗流程

v2: 支持多国标题存储 — optimized_titles / description_snippets / ai_tags_by_lang 均为 JSON
"""

import sqlite3
import time
import json
from pathlib import Path
from datetime import datetime, timezone
import os
from typing import Optional, Any

from .config import BASE_DIR

MEMORY_DB_PATH = BASE_DIR / "data" / "product_memory.db"

# 汇率可通过环境变量覆盖（ADFEED_CNY_USD / ADFEED_USD_EUR）
USD_RATE_CNY = float(os.getenv("ADFEED_CNY_USD", "7.25"))
USD_RATE_EUR = float(os.getenv("ADFEED_USD_EUR", "0.92"))
SUPPORTED_COUNTRIES = ["US", "DE", "FR", "ES", "IT"]


def _safe_json_dumps(obj: Any) -> str:
    return json.dumps(obj if obj is not None else {}, ensure_ascii=False)


def _safe_json_loads(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return {}
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            return val if isinstance(val, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _get_conn() -> sqlite3.Connection:
    MEMORY_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(MEMORY_DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    _init_schema(conn)
    return conn


def _init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_memory (
            product_id       TEXT PRIMARY KEY,
            item_group_id    TEXT DEFAULT '',
            original_title   TEXT,
            description      TEXT,
            category         TEXT,
            brand            TEXT DEFAULT '',
            material         TEXT,
            color            TEXT,
            size             TEXT DEFAULT '',
            size_system      TEXT DEFAULT '',
            size_type        TEXT DEFAULT '',
            gender           TEXT DEFAULT '',
            age_group        TEXT DEFAULT 'adult',
            gtin             TEXT DEFAULT '',
            mpn              TEXT DEFAULT '',
            identifier_exists TEXT DEFAULT 'no',
            image_url        TEXT,
            additional_images TEXT DEFAULT '',
            -- 定价
            price_cny        REAL,
            price_usd        REAL,
            sale_price_usd   REAL DEFAULT 0,
            sale_price_effective_date TEXT DEFAULT '',
            -- 库存
            inventory        INTEGER DEFAULT 0,
            -- 分类
            gpc_code         TEXT,
            gpc_path         TEXT,
            -- 活动分层
            custom_label_0   TEXT DEFAULT '',
            custom_label_1   TEXT DEFAULT '',
            custom_label_2   TEXT DEFAULT '',
            custom_label_3   TEXT DEFAULT '',
            custom_label_4   TEXT DEFAULT '',
            -- 物流
            shipping_country TEXT DEFAULT '',
            shipping_price   REAL DEFAULT 0,
            shipping_weight  TEXT DEFAULT '',
            min_handling_time INTEGER DEFAULT 0,
            max_handling_time INTEGER DEFAULT 0,
            -- 合规
            adult            TEXT DEFAULT 'no',
            multipack        INTEGER DEFAULT 0,
            is_bundle        TEXT DEFAULT 'no',
            tax              TEXT DEFAULT '',
            energy_efficiency_class TEXT DEFAULT '',
            unit_pricing_measure      TEXT DEFAULT '',
            unit_pricing_base_measure  TEXT DEFAULT '',
            -- AI 生成
            optimized_titles      TEXT DEFAULT '{}',
            ai_tags_by_lang       TEXT DEFAULT '{}',
            description_snippets  TEXT DEFAULT '{}',
            source_country   TEXT DEFAULT 'CN',
            target_countries TEXT DEFAULT '["US"]',
            last_ai_clean_at TEXT,
            created_at       TEXT,
            updated_at       TEXT,
            version          INTEGER DEFAULT 1
        )
    """)

    # 迁移旧 optimized_title → optimized_titles + 添加缺失字段
    try:
        col_info = conn.execute("PRAGMA table_info(product_memory)").fetchall()
        col_names = [c[1] for c in col_info]
        if "optimized_title" in col_names and "optimized_titles" in col_names:
            conn.execute("""
                UPDATE product_memory 
                SET optimized_titles = json_object('US', COALESCE(optimized_title, original_title))
                WHERE (optimized_titles = '{}' OR optimized_titles IS NULL)
                  AND optimized_title IS NOT NULL AND optimized_title != ''
            """)
            conn.commit()
        # 迁移：添加 brand 列
        if "brand" not in col_names:
            conn.execute("ALTER TABLE product_memory ADD COLUMN brand TEXT DEFAULT ''")
            conn.commit()
        # 迁移：添加所有新字段
        col_migrations = [
            ("brand", "TEXT DEFAULT ''"),
            ("item_group_id", "TEXT DEFAULT ''"),
            ("size", "TEXT DEFAULT ''"),
            ("size_system", "TEXT DEFAULT ''"),
            ("size_type", "TEXT DEFAULT ''"),
            ("gender", "TEXT DEFAULT ''"),
            ("age_group", "TEXT DEFAULT 'adult'"),
            ("gtin", "TEXT DEFAULT ''"),
            ("mpn", "TEXT DEFAULT ''"),
            ("identifier_exists", "TEXT DEFAULT 'no'"),
            ("additional_images", "TEXT DEFAULT ''"),
            ("sale_price_usd", "REAL DEFAULT 0"),
            ("sale_price_effective_date", "TEXT DEFAULT ''"),
            ("custom_label_0", "TEXT DEFAULT ''"),
            ("custom_label_1", "TEXT DEFAULT ''"),
            ("custom_label_2", "TEXT DEFAULT ''"),
            ("custom_label_3", "TEXT DEFAULT ''"),
            ("custom_label_4", "TEXT DEFAULT ''"),
            ("shipping_country", "TEXT DEFAULT ''"),
            ("shipping_price", "REAL DEFAULT 0"),
            ("shipping_weight", "TEXT DEFAULT ''"),
            ("min_handling_time", "INTEGER DEFAULT 0"),
            ("max_handling_time", "INTEGER DEFAULT 0"),
            ("adult", "TEXT DEFAULT 'no'"),
            ("multipack", "INTEGER DEFAULT 0"),
            ("is_bundle", "TEXT DEFAULT 'no'"),
            ("tax", "TEXT DEFAULT ''"),
            ("energy_efficiency_class", "TEXT DEFAULT ''"),
            ("unit_pricing_measure", "TEXT DEFAULT ''"),
            ("unit_pricing_base_measure", "TEXT DEFAULT ''"),
        ]
        for col, col_type in col_migrations:
            if col not in col_names:
                conn.execute(f"ALTER TABLE product_memory ADD COLUMN {col} {col_type}")
                conn.commit()
    except Exception:
        pass

    conn.execute("CREATE INDEX IF NOT EXISTS idx_pm_updated ON product_memory(updated_at)")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS product_memory_log (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id    TEXT,
            action        TEXT,
            old_price     REAL,
            new_price     REAL,
            old_inventory INTEGER,
            new_inventory INTEGER,
            token_cost    INTEGER DEFAULT 0,
            created_at    TEXT
        )
    """)

    conn.commit()


def lookup(product_id: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM product_memory WHERE product_id = ?", (product_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    d["optimized_titles"] = _safe_json_loads(d.get("optimized_titles"))
    d["ai_tags_by_lang"] = _safe_json_loads(d.get("ai_tags_by_lang"))
    d["description_snippets"] = _safe_json_loads(d.get("description_snippets"))
    return d


def get_title_for_country(product_id: str, country: str) -> str:
    existing = lookup(product_id)
    if not existing:
        return ""
    titles = existing.get("optimized_titles", {})
    return titles.get(country.upper(), "")


def get_description_snippet(product_id: str, country: str) -> str:
    existing = lookup(product_id)
    if not existing:
        return ""
    snippets = existing.get("description_snippets", {})
    return snippets.get(country.upper(), "")


def get_ai_tags(product_id: str, country: str) -> list:
    existing = lookup(product_id)
    if not existing:
        return []
    tags = existing.get("ai_tags_by_lang", {})
    result = tags.get(country.upper(), [])
    if isinstance(result, str):
        try:
            result = json.loads(result)
        except Exception:
            result = []
    return result if isinstance(result, list) else []


def cny_to_usd(price_cny: float) -> float:
    return round(price_cny / USD_RATE_CNY, 2)


def classify_row(
    product_id: str,
    title: str,
    price_cny: float,
    inventory: int,
    description: str = "",
    category: str = "",
    material: str = "",
    color: str = "",
    image_url: str = "",
    target_countries: list[str] = None,
) -> dict:
    price_usd = cny_to_usd(price_cny) if price_cny > 0 else 0.0
    existing = lookup(product_id)
    target_list = target_countries or ["US"]

    if existing is None:
        return {
            "is_new": True, "action": "ai_full_clean",
            "token_cost_estimate": 5000 * len(target_list),
            "existing": None, "price_usd": price_usd,
            "needs_reclean_for": target_list,
        }

    old_price = existing.get("price_cny", 0)
    old_inventory = existing.get("inventory", 0)
    old_title = existing.get("original_title", "")

    changed = []
    if abs(price_cny - old_price) > 0.01:
        changed.append("price")
    if inventory != old_inventory:
        changed.append("inventory")
    if title != old_title:
        changed.append("title")

    existing_titles = existing.get("optimized_titles", {})
    missing_countries = [c.upper() for c in target_list if c.upper() not in existing_titles or not existing_titles[c.upper()]]

    if not changed and not missing_countries:
        return {
            "is_new": False, "action": "skip",
            "token_cost_estimate": 0, "existing": existing,
            "price_usd": price_usd, "needs_reclean_for": [],
        }

    if not changed and missing_countries:
        return {
            "is_new": False, "action": "partial_reclean",
            "token_cost_estimate": 5000 * len(missing_countries),
            "existing": existing, "price_usd": price_usd,
            "needs_reclean_for": missing_countries,
        }

    if changed == ["price"] or changed == ["inventory"] or changed == ["price", "inventory"]:
        return {
            "is_new": False, "action": "price_inventory_update",
            "token_cost_estimate": 0, "existing": existing,
            "price_usd": price_usd, "needs_reclean_for": [],
        }

    return {
        "is_new": True, "action": "ai_full_clean",
        "token_cost_estimate": 5000 * len(target_list),
        "existing": existing, "price_usd": price_usd,
        "needs_reclean_for": target_list,
    }


def save_new_product(
    product_id: str, title: str, price_cny: float, inventory: int,
    description: str = "", category: str = "", brand: str = "",
    material: str = "", color: str = "",
    size: str = "", size_system: str = "", size_type: str = "",
    gender: str = "", age_group: str = "adult",
    gtin: str = "", mpn: str = "", identifier_exists: str = "no",
    image_url: str = "", additional_images: str = "",
    sale_price_usd: float = 0, sale_price_effective_date: str = "",
    custom_label_0: str = "", custom_label_1: str = "",
    custom_label_2: str = "", custom_label_3: str = "", custom_label_4: str = "",
    shipping_country: str = "", shipping_price: float = 0,
    shipping_weight: str = "", min_handling_time: int = 0, max_handling_time: int = 0,
    adult: str = "no", multipack: int = 0, is_bundle: str = "no",
    tax: str = "",
    energy_efficiency_class: str = "",
    unit_pricing_measure: str = "", unit_pricing_base_measure: str = "",
    gpc_code: str = "", gpc_path: str = "",
    item_group_id: str = "",
    optimized_titles: dict[str, str] = None,
    ai_tags_by_lang: dict[str, list] = None,
    description_snippets: dict[str, str] = None,
    target_countries: list[str] = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    price_usd = cny_to_usd(price_cny)
    tgt = target_countries or ["US"]

    conn = _get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO product_memory
        (product_id, item_group_id, original_title, description, category,
         brand, material, color,
         size, size_system, size_type, gender, age_group,
         gtin, mpn, identifier_exists,
         image_url, additional_images,
         price_cny, price_usd, sale_price_usd, sale_price_effective_date,
         inventory,
         gpc_code, gpc_path,
         custom_label_0, custom_label_1, custom_label_2, custom_label_3, custom_label_4,
         shipping_country, shipping_price, shipping_weight,
         min_handling_time, max_handling_time,
         adult, multipack, is_bundle, tax,
         energy_efficiency_class, unit_pricing_measure, unit_pricing_base_measure,
         optimized_titles, ai_tags_by_lang, description_snippets,
         source_country, target_countries,
         last_ai_clean_at, created_at, updated_at, version)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?,
                ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?, 1)
    """, (
        product_id, item_group_id or "",
        title, description, category, brand or "", material, color,
        size or "", size_system or "", size_type or "",
        gender or "", age_group or "adult",
        gtin or "", mpn or "", identifier_exists or "no",
        image_url, additional_images or "",
        price_cny, price_usd, sale_price_usd or 0, sale_price_effective_date or "",
        inventory,
        gpc_code, gpc_path,
        custom_label_0 or "", custom_label_1 or "", custom_label_2 or "",
        custom_label_3 or "", custom_label_4 or "",
        shipping_country or "", shipping_price or 0, shipping_weight or "",
        min_handling_time or 0, max_handling_time or 0,
        adult or "no", multipack or 0, is_bundle or "no", tax or "",
        energy_efficiency_class or "", unit_pricing_measure or "", unit_pricing_base_measure or "",
        _safe_json_dumps(optimized_titles or {}),
        _safe_json_dumps(ai_tags_by_lang or {}),
        _safe_json_dumps(description_snippets or {}),
        "CN", _safe_json_dumps(tgt),
        now, now, now,
    ))
    _log_action(conn, product_id, "new_ai_clean", 0, price_cny, 0, inventory, token_cost=5000 * len(tgt))
    conn.commit()
    conn.close()
    return {"product_id": product_id, "price_usd": price_usd, "action": "created"}


def update_multi_country_titles(
    product_id: str,
    optimized_titles: dict[str, str],
    ai_tags_by_lang: dict[str, list],
    description_snippets: dict[str, str],
    gpc_code: str = None,
    gpc_path: str = None,
) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    existing = lookup(product_id)
    if not existing:
        return {"product_id": product_id, "error": "not_found"}

    existing_titles = existing.get("optimized_titles", {})
    existing_tags = existing.get("ai_tags_by_lang", {})
    existing_snippets = existing.get("description_snippets", {})

    existing_titles.update(optimized_titles or {})
    existing_tags.update(ai_tags_by_lang or {})
    existing_snippets.update(description_snippets or {})

    conn = _get_conn()
    conn.execute("""
        UPDATE product_memory SET optimized_titles=?, ai_tags_by_lang=?,
        description_snippets=?, last_ai_clean_at=?, version=version+1
        WHERE product_id=?
    """, (
        _safe_json_dumps(existing_titles),
        _safe_json_dumps(existing_tags),
        _safe_json_dumps(existing_snippets),
        now, product_id,
    ))

    if gpc_code:
        conn.execute("UPDATE product_memory SET gpc_code=? WHERE product_id=?", (gpc_code, product_id))
    if gpc_path:
        conn.execute("UPDATE product_memory SET gpc_path=? WHERE product_id=?", (gpc_path, product_id))

    _log_action(conn, product_id, "partial_reclean", 0, 0, 0, 0,
                token_cost=5000 * len(optimized_titles or {}))
    conn.commit()
    conn.close()
    return {"product_id": product_id, "action": "partial_reclean",
            "countries_updated": list(optimized_titles.keys())}


def update_price_inventory(product_id: str, price_cny: float, inventory: int) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    price_usd = cny_to_usd(price_cny)
    conn = _get_conn()
    old = conn.execute(
        "SELECT price_cny, inventory FROM product_memory WHERE product_id = ?", (product_id,)
    ).fetchone()
    if old is None:
        conn.close()
        return {"product_id": product_id, "error": "not_found"}
    old_price, old_inventory = old["price_cny"], old["inventory"]
    conn.execute("""
        UPDATE product_memory SET price_cny=?, price_usd=?, inventory=?,
        updated_at=?, version=version+1 WHERE product_id=?
    """, (price_cny, price_usd, inventory, now, product_id))
    _log_action(conn, product_id, "price_inventory_update", old_price, price_cny, old_inventory, inventory, token_cost=0)
    conn.commit()
    conn.close()
    return {"product_id": product_id, "price_usd": price_usd, "action": "updated", "token_cost": 0}


def _log_action(conn, product_id, action, old_price, new_price, old_inventory, new_inventory, token_cost=0):
    conn.execute("""
        INSERT INTO product_memory_log
        (product_id, action, old_price, new_price, old_inventory, new_inventory, token_cost, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (product_id, action, old_price, new_price, old_inventory, new_inventory,
          token_cost, datetime.now(timezone.utc).isoformat()))


def get_all_active(target_country: str = None) -> list[dict]:
    conn = _get_conn()
    if target_country:
        rows = conn.execute(
            "SELECT * FROM product_memory WHERE target_countries LIKE ? ORDER BY updated_at DESC",
            (f"%{target_country}%",)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM product_memory ORDER BY updated_at DESC").fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["optimized_titles"] = _safe_json_loads(d.get("optimized_titles"))
        d["ai_tags_by_lang"] = _safe_json_loads(d.get("ai_tags_by_lang"))
        d["description_snippets"] = _safe_json_loads(d.get("description_snippets"))
        result.append(d)
    return result


def get_stats() -> dict:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM product_memory").fetchone()[0]
    ai_cleans = conn.execute(
        "SELECT COUNT(*) FROM product_memory_log WHERE action='new_ai_clean'"
    ).fetchone()[0]
    price_updates = conn.execute(
        "SELECT COUNT(*) FROM product_memory_log WHERE action='price_inventory_update'"
    ).fetchone()[0]
    partial = conn.execute(
        "SELECT COUNT(*) FROM product_memory_log WHERE action='partial_reclean'"
    ).fetchone()[0]
    conn.close()
    return {
        "total_products": total,
        "total_ai_cleans": ai_cleans,
        "total_partial_recleans": partial,
        "total_zero_token_updates": price_updates,
        "estimated_tokens_saved": price_updates * 5000,
    }


def get_recent(limit: int = 20) -> list[dict]:
    """获取最近处理的商品结果（用于 Web 页面结果展示）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM product_memory ORDER BY updated_at DESC LIMIT ?",
        (limit,)
    ).fetchall()
    cols = [d[0] for d in conn.execute("PRAGMA table_info(product_memory)").fetchall()]
    conn.close()
    results = []
    for row in rows:
        item = dict(zip(cols, row))
        item["optimized_titles"] = _safe_json_loads(item.get("optimized_titles"))
        item["ai_tags_by_lang"] = _safe_json_loads(item.get("ai_tags_by_lang"))
        item["description_snippets"] = _safe_json_loads(item.get("description_snippets"))
        results.append(item)
    return results


def batch_process(products: list[dict]) -> dict:
    result = {"new_products": [], "partial_reclean": [], "price_updates": [], "skipped": [], "stats": {"total": len(products)}}
    for p in products:
        c = classify_row(
            product_id=p.get("product_id", ""), title=p.get("title", ""),
            price_cny=p.get("price_cny", 0), inventory=p.get("inventory", 0),
            description=p.get("description", ""), category=p.get("category", ""),
            material=p.get("material", ""), color=p.get("color", ""),
            image_url=p.get("image_url", ""),
            target_countries=p.get("target_countries", ["US"]),
        )
        p["_classification"] = c
        if c["action"] == "ai_full_clean":
            result["new_products"].append(p)
        elif c["action"] == "partial_reclean":
            result["partial_reclean"].append(p)
        elif c["action"] == "price_inventory_update":
            update_price_inventory(p["product_id"], p.get("price_cny", 0), p.get("inventory", 0))
            result["price_updates"].append(p)
        else:
            result["skipped"].append(p)
    result["stats"]["new"] = len(result["new_products"])
    result["stats"]["partial"] = len(result["partial_reclean"])
    result["stats"]["price_updates"] = len(result["price_updates"])
    result["stats"]["skipped"] = len(result["skipped"])
    result["stats"]["tokens_estimated"] = (len(result["new_products"]) + len(result["partial_reclean"])) * 5000
    return result
