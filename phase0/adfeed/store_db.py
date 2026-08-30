"""AdFeed AI — 多店铺多国家持久化 Feed 数据库层

管理店铺、产品、变体、Feed 配置和生成记录。
与现有 db.py 共享同一个 SQLite 数据库（webapp.db）。

核心表：
- stores: 店铺信息（Shopify App 安装后创建）
- products: 产品主表（从 Shopify 同步或 Excel 导入）
- product_variants: 变体表（颜色×尺码展开后）
- feed_configs: Feed 配置表（每店×每国一条）
- feed_files: 生成的 XML 文件记录
"""

import uuid
import json
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional

from .db import _conn, DATA_DIR


# ─────────────────────────────────────────────
# Schema 定义
# ─────────────────────────────────────────────

STORE_SCHEMA = """
-- 店铺表（Shopify App 安装后创建）
CREATE TABLE IF NOT EXISTS stores (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    shopify_domain TEXT UNIQUE NOT NULL,  -- mystore.myshopify.com
    shop_name TEXT,
    access_token TEXT,
    site_url TEXT,                        -- 前端站点URL（用于拼接Feed link）
    default_brand TEXT,
    default_currency TEXT DEFAULT 'USD',
    plan TEXT DEFAULT 'free',
    quota_total INTEGER DEFAULT 3,
    quota_used INTEGER DEFAULT 0,
    subscription_id TEXT,
    billing_status TEXT DEFAULT 'none',   -- none / active / cancelled / frozen
    status TEXT DEFAULT 'active',         -- active / suspended / archived
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 产品主表（从 Shopify 同步或 Excel 导入）
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    shopify_product_id TEXT,              -- Shopify 原始ID
    handle TEXT,                          -- URL slug
    title TEXT,
    vendor TEXT,
    product_type TEXT,
    brand TEXT,
    material TEXT,
    gender TEXT,                          -- male / female / unisex
    age_group TEXT,                       -- adult / kids / toddler
    gpc_code TEXT,                        -- 匹配后的GPC ID
    gpc_path TEXT,
    gpc_confidence REAL,
    gpc_source TEXT,                      -- keyword / llm / manual
    image_url TEXT,
    additional_images TEXT,               -- JSON array
    description TEXT,                     -- 原始描述
    optimized_title TEXT,                 -- AI优化标题（默认/主语言）
    cleaned_title TEXT,                   -- AI清洗后标题（多语种JSON）
    cleaned_description TEXT,             -- AI清洗后描述（多语种JSON）
    feed_enabled INTEGER DEFAULT 0,       -- 1=加入Google广告Feed, 0=不进XML
    ai_status TEXT DEFAULT 'raw',         -- raw=待清洗 / processing=清洗中 / ready=已就绪
    status TEXT DEFAULT 'active',         -- active / archived / error
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 变体表（每个产品多个变体：颜色×尺码）
-- SKU uniqueness is per product: suppliers often reuse the same SKU on
-- active + draft duplicates; a global UNIQUE stole variants across products.
CREATE TABLE IF NOT EXISTS product_variants (
    id TEXT PRIMARY KEY,
    product_id TEXT NOT NULL REFERENCES products(id),
    shopify_variant_id TEXT,
    sku TEXT,
    title TEXT,                           -- 如 "White / S"
    color TEXT,
    size TEXT,
    price REAL,
    compare_at_price REAL,
    inventory INTEGER DEFAULT 0,
    weight REAL,
    weight_unit TEXT DEFAULT 'kg',
    image_url TEXT,
    feed_image_url TEXT,                  -- Feed override (not written back to Shopify)
    barcode TEXT,                         -- UPC/EAN（如有）
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, sku)
);

-- Feed 配置表（每店×每国一条）
CREATE TABLE IF NOT EXISTS feed_configs (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    country TEXT NOT NULL,                -- US / DE / FR / ES / IT
    currency TEXT DEFAULT 'USD',
    language TEXT DEFAULT 'en',
    site_link TEXT,                       -- 该国站点URL
    auto_sync INTEGER DEFAULT 1,
    last_synced_at TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(store_id, country)
);

-- Feed 文件记录表（生成的XML）
CREATE TABLE IF NOT EXISTS feed_files (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    country TEXT NOT NULL,
    platform TEXT DEFAULT 'google',       -- google / meta / tiktok
    file_path TEXT NOT NULL,              -- 磁盘路径
    feed_url TEXT NOT NULL,               -- 公开访问URL
    item_count INTEGER DEFAULT 0,
    file_size INTEGER DEFAULT 0,
    generated_at TEXT,
    expires_at TEXT,                      -- 可选过期时间
    status TEXT DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Merchant-removed SKUs (stay out of feed on regenerate until re-added)
CREATE TABLE IF NOT EXISTS feed_excluded_skus (
    store_id TEXT NOT NULL REFERENCES stores(id),
    platform TEXT NOT NULL DEFAULT 'google',
    country TEXT NOT NULL,
    sku TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (store_id, platform, country, sku)
);

-- 平台×语言 优化资产（计费单元）
CREATE TABLE IF NOT EXISTS product_assets (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    product_id TEXT NOT NULL REFERENCES products(id),
    platform TEXT NOT NULL,               -- google / meta / tiktok
    language TEXT NOT NULL,               -- US / DE / FR / ES / IT
    title TEXT,
    description TEXT,
    tags_json TEXT,
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(product_id, platform, language)
);

-- 配额扣费明细
CREATE TABLE IF NOT EXISTS usage_ledger (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    job_id TEXT,
    sku TEXT,
    platform TEXT NOT NULL,
    language TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- App 生成任务（店铺维度）
CREATE TABLE IF NOT EXISTS store_jobs (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    status TEXT DEFAULT 'pending',        -- pending / processing / completed / failed
    platforms TEXT NOT NULL DEFAULT '["google"]',
    languages TEXT NOT NULL DEFAULT '["US"]',
    product_ids TEXT,                     -- JSON array
    total_units INTEGER DEFAULT 0,        -- SKU×platform×language
    done_units INTEGER DEFAULT 0,
    ok_units INTEGER DEFAULT 0,
    fail_units INTEGER DEFAULT 0,
    result_json TEXT,
    error_msg TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_products_store ON products(store_id, status);
CREATE INDEX IF NOT EXISTS idx_products_gpc ON products(gpc_code);
CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id, status);
CREATE INDEX IF NOT EXISTS idx_variants_sku ON product_variants(sku);
CREATE INDEX IF NOT EXISTS idx_feed_configs_store ON feed_configs(store_id, country);
CREATE INDEX IF NOT EXISTS idx_feed_files_store ON feed_files(store_id, country);
CREATE INDEX IF NOT EXISTS idx_product_assets_store ON product_assets(store_id, platform, language);
CREATE INDEX IF NOT EXISTS idx_usage_ledger_store ON usage_ledger(store_id, created_at);
CREATE INDEX IF NOT EXISTS idx_store_jobs_store ON store_jobs(store_id, created_at DESC);

-- Google OAuth + Merchant Center issues + Ads metrics (read-only loop)
CREATE TABLE IF NOT EXISTS google_oauth_tokens (
    store_id TEXT PRIMARY KEY REFERENCES stores(id),
    refresh_token_enc TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS google_merchant_accounts (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    merchant_id TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    is_selected INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(store_id, merchant_id)
);

CREATE TABLE IF NOT EXISTS gmc_product_issues (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    merchant_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    product_id_internal TEXT,
    status TEXT NOT NULL DEFAULT '',
    reason_code TEXT DEFAULT '',
    reason_text TEXT DEFAULT '',
    raw_json TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS ads_metrics_daily (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    ads_customer_id TEXT NOT NULL,
    date TEXT NOT NULL,
    offer_id TEXT,
    campaign_id TEXT,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    cost_micros INTEGER DEFAULT 0,
    conversions REAL DEFAULT 0,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_gmc_issues_store ON gmc_product_issues(store_id, merchant_id);
CREATE INDEX IF NOT EXISTS idx_gmc_merchants_store ON google_merchant_accounts(store_id);
CREATE INDEX IF NOT EXISTS idx_ads_metrics_store ON ads_metrics_daily(store_id, ads_customer_id, date);

-- Meta Catalog (OAuth + selected catalogs)
CREATE TABLE IF NOT EXISTS meta_oauth_tokens (
    store_id TEXT PRIMARY KEY REFERENCES stores(id),
    access_token_enc TEXT NOT NULL,
    scopes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS meta_catalogs (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    catalog_id TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    product_feed_id TEXT DEFAULT '',
    is_selected INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(store_id, catalog_id)
);

CREATE INDEX IF NOT EXISTS idx_meta_catalogs_store ON meta_catalogs(store_id);

-- TikTok Shop (OAuth + selected shops)
CREATE TABLE IF NOT EXISTS tiktok_oauth_tokens (
    store_id TEXT PRIMARY KEY REFERENCES stores(id),
    refresh_token_enc TEXT NOT NULL,
    access_token_enc TEXT NOT NULL DEFAULT '',
    scopes TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tiktok_shops (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    shop_id TEXT NOT NULL,
    display_name TEXT DEFAULT '',
    feed_url TEXT DEFAULT '',
    cipher TEXT DEFAULT '',
    is_selected INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(store_id, shop_id)
);

CREATE INDEX IF NOT EXISTS idx_tiktok_shops_store ON tiktok_shops(store_id);

CREATE TABLE IF NOT EXISTS meta_product_issues (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    catalog_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    product_id_internal TEXT,
    status TEXT NOT NULL DEFAULT '',
    reason_code TEXT DEFAULT '',
    reason_text TEXT DEFAULT '',
    raw_json TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tiktok_product_issues (
    id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(id),
    shop_id TEXT NOT NULL,
    offer_id TEXT NOT NULL,
    product_id_internal TEXT,
    status TEXT NOT NULL DEFAULT '',
    reason_code TEXT DEFAULT '',
    reason_text TEXT DEFAULT '',
    raw_json TEXT,
    synced_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_meta_issues_store ON meta_product_issues(store_id, catalog_id);
CREATE INDEX IF NOT EXISTS idx_tiktok_issues_store ON tiktok_product_issues(store_id, shop_id);
"""


def init_store_schema():
    """初始化店铺相关表结构"""
    with _conn() as c:
        c.executescript(STORE_SCHEMA)
        c.commit()

        # 迁移：为已存在的表添加新字段
        migrations = [
            "ALTER TABLE products ADD COLUMN cleaned_title TEXT",
            "ALTER TABLE products ADD COLUMN cleaned_description TEXT",
            "ALTER TABLE products ADD COLUMN feed_enabled INTEGER DEFAULT 0",
            "ALTER TABLE products ADD COLUMN ai_status TEXT DEFAULT 'raw'",
            "ALTER TABLE stores ADD COLUMN plan TEXT DEFAULT 'free'",
            "ALTER TABLE stores ADD COLUMN quota_total INTEGER DEFAULT 3",
            "ALTER TABLE stores ADD COLUMN quota_used INTEGER DEFAULT 0",
            "ALTER TABLE stores ADD COLUMN subscription_id TEXT",
            "ALTER TABLE stores ADD COLUMN billing_status TEXT DEFAULT 'none'",
            "ALTER TABLE feed_files ADD COLUMN platform TEXT DEFAULT 'google'",
            "ALTER TABLE product_variants ADD COLUMN feed_image_url TEXT",
            "ALTER TABLE product_variants ADD COLUMN feed_title TEXT",
            "ALTER TABLE stores ADD COLUMN refresh_token TEXT",
            "ALTER TABLE stores ADD COLUMN token_expires_at TEXT",
        ]
        for sql in migrations:
            try:
                c.execute(sql)
            except Exception:
                pass  # 字段已存在，忽略
        c.commit()

        # 迁移后创建索引（依赖新字段）
        try:
            c.execute("CREATE INDEX IF NOT EXISTS idx_products_feed ON products(store_id, feed_enabled, ai_status)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_product_assets_store ON product_assets(store_id, platform, language)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_usage_ledger_store ON usage_ledger(store_id, created_at)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_store_jobs_store ON store_jobs(store_id, created_at DESC)")
            c.commit()
        except Exception:
            pass

        _migrate_variant_sku_scope(c)

    print("[StoreDB] 店铺数据库表已初始化")


def _migrate_variant_sku_scope(c) -> None:
    """Drop global UNIQUE(sku); keep UNIQUE(product_id, sku). Idempotent."""
    try:
        row = c.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='product_variants'"
        ).fetchone()
        ddl = (row[0] if row else "") or ""
        # Already migrated when CREATE has UNIQUE(product_id, sku) and no lone sku UNIQUE.
        if "UNIQUE(product_id, sku)" in ddl.replace(" ", "") or "UNIQUE (product_id, sku)" in ddl:
            if "sku TEXT UNIQUE" not in ddl and "sku TEXT\n" in ddl.replace("  ", " "):
                return
        # Detect legacy global unique: "sku TEXT UNIQUE"
        if "sku TEXT UNIQUE" not in ddl and "sku TEXT UNIQUE," not in ddl:
            # Ensure composite unique index exists even if CREATE IF NOT EXISTS skipped alter
            try:
                c.execute(
                    "CREATE UNIQUE INDEX IF NOT EXISTS idx_variants_product_sku "
                    "ON product_variants(product_id, sku)"
                )
                c.commit()
            except Exception:
                pass
            return

        c.execute("ALTER TABLE product_variants RENAME TO product_variants_sku_mig")
        c.execute(
            """
            CREATE TABLE product_variants (
                id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL REFERENCES products(id),
                shopify_variant_id TEXT,
                sku TEXT,
                title TEXT,
                color TEXT,
                size TEXT,
                price REAL,
                compare_at_price REAL,
                inventory INTEGER DEFAULT 0,
                weight REAL,
                weight_unit TEXT DEFAULT 'kg',
                image_url TEXT,
                feed_image_url TEXT,
                barcode TEXT,
                status TEXT DEFAULT 'active',
                created_at TEXT NOT NULL DEFAULT (datetime('now')),
                updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                feed_title TEXT,
                UNIQUE(product_id, sku)
            )
            """
        )
        c.execute(
            """
            INSERT INTO product_variants (
                id, product_id, shopify_variant_id, sku, title, color, size,
                price, compare_at_price, inventory, weight, weight_unit,
                image_url, feed_image_url, barcode, status, created_at, updated_at,
                feed_title
            )
            SELECT
                id, product_id, shopify_variant_id, sku, title, color, size,
                price, compare_at_price, inventory, weight, weight_unit,
                image_url, feed_image_url, barcode, status, created_at, updated_at,
                feed_title
            FROM product_variants_sku_mig
            """
        )
        c.execute("DROP TABLE product_variants_sku_mig")
        c.execute("CREATE INDEX IF NOT EXISTS idx_variants_product ON product_variants(product_id, status)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_variants_sku ON product_variants(sku)")
        c.commit()
    except Exception:
        pass


# ─────────────────────────────────────────────
# Data Classes
# ─────────────────────────────────────────────

@dataclass
class Store:
    id: str
    user_id: str
    shopify_domain: str
    shop_name: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[str] = None
    site_url: Optional[str] = None
    default_brand: Optional[str] = None
    default_currency: str = "USD"
    plan: str = "free"
    quota_total: int = 3
    quota_used: int = 0
    subscription_id: Optional[str] = None
    billing_status: str = "none"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""

    @property
    def quota_remaining(self) -> int:
        return max(0, self.quota_total - self.quota_used)


@dataclass
class Product:
    id: str
    store_id: str
    title: str
    shopify_product_id: Optional[str] = None
    handle: Optional[str] = None
    vendor: Optional[str] = None
    product_type: Optional[str] = None
    brand: Optional[str] = None
    material: Optional[str] = None
    gender: Optional[str] = None
    age_group: Optional[str] = None
    gpc_code: Optional[str] = None
    gpc_path: Optional[str] = None
    gpc_confidence: float = 0.0
    gpc_source: Optional[str] = None
    image_url: Optional[str] = None
    additional_images: Optional[str] = None
    description: Optional[str] = None
    optimized_title: Optional[str] = None
    cleaned_title: Optional[str] = None
    cleaned_description: Optional[str] = None
    feed_enabled: int = 0
    ai_status: str = "raw"
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ProductVariant:
    id: str
    product_id: str
    sku: str
    shopify_variant_id: Optional[str] = None
    title: Optional[str] = None
    color: Optional[str] = None
    size: Optional[str] = None
    price: float = 0.0
    compare_at_price: Optional[float] = None
    inventory: int = 0
    weight: Optional[float] = None
    weight_unit: str = "kg"
    image_url: Optional[str] = None
    feed_image_url: Optional[str] = None
    feed_title: Optional[str] = None
    barcode: Optional[str] = None
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class FeedConfig:
    id: str
    store_id: str
    country: str
    currency: str = "USD"
    language: str = "en"
    site_link: Optional[str] = None
    auto_sync: bool = True
    last_synced_at: Optional[str] = None
    status: str = "active"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class FeedFile:
    id: str
    store_id: str
    country: str
    file_path: str
    feed_url: str
    item_count: int = 0
    file_size: int = 0
    generated_at: Optional[str] = None
    status: str = "active"
    platform: str = "google"
    created_at: str = ""
    updated_at: str = ""


@dataclass
class ProductAsset:
    id: str
    store_id: str
    product_id: str
    platform: str
    language: str
    title: Optional[str] = None
    description: Optional[str] = None
    tags_json: Optional[str] = None
    updated_at: str = ""
    created_at: str = ""


@dataclass
class StoreJob:
    id: str
    store_id: str
    status: str = "pending"
    platforms: str = '["google"]'
    languages: str = '["US"]'
    product_ids: Optional[str] = None
    total_units: int = 0
    done_units: int = 0
    ok_units: int = 0
    fail_units: int = 0
    result_json: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""


def _row_to_store(row) -> Store:
    keys = row.keys() if hasattr(row, "keys") else []
    return Store(
        id=row["id"], user_id=row["user_id"], shopify_domain=row["shopify_domain"],
        shop_name=row["shop_name"], access_token=row["access_token"],
        refresh_token=row["refresh_token"] if "refresh_token" in keys else None,
        token_expires_at=row["token_expires_at"] if "token_expires_at" in keys else None,
        site_url=row["site_url"], default_brand=row["default_brand"],
        default_currency=row["default_currency"] or "USD",
        plan=row["plan"] if "plan" in keys else "free",
        quota_total=row["quota_total"] if "quota_total" in keys else 3,
        quota_used=row["quota_used"] if "quota_used" in keys else 0,
        subscription_id=row["subscription_id"] if "subscription_id" in keys else None,
        billing_status=row["billing_status"] if "billing_status" in keys else "none",
        status=row["status"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


# ─────────────────────────────────────────────
# Store CRUD
# ─────────────────────────────────────────────

def create_store(user_id: str, shopify_domain: str, shop_name: str = None,
                 access_token: str = None, site_url: str = None,
                 plan: str = "free", quota_total: int = 3) -> Store:
    """创建新店铺"""
    sid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            """INSERT INTO stores
               (id, user_id, shopify_domain, shop_name, access_token, site_url, plan, quota_total, quota_used, billing_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, 'none')""",
            (sid, user_id, shopify_domain, shop_name, access_token, site_url, plan, quota_total),
        )
        c.commit()
    return get_store(sid)


def get_store(store_id: str) -> Optional[Store]:
    """获取店铺信息"""
    with _conn() as c:
        row = c.execute("SELECT * FROM stores WHERE id = ?", (store_id,)).fetchone()
    if not row:
        return None
    return _row_to_store(row)


def get_store_by_subscription_id(subscription_id: str) -> Optional[Store]:
    """Lookup store by Shopify AppSubscription GID."""
    if not subscription_id:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM stores WHERE subscription_id = ?",
            (subscription_id,),
        ).fetchone()
    return _row_to_store(row) if row else None


def get_store_by_domain(shopify_domain: str) -> Optional[Store]:
    """通过 Shopify domain 获取店铺"""
    with _conn() as c:
        row = c.execute("SELECT * FROM stores WHERE shopify_domain = ?", (shopify_domain,)).fetchone()
    if not row:
        return None
    return get_store(row["id"])


def list_stores(user_id: str) -> list[Store]:
    """列出用户的所有店铺"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM stores WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()
    return [get_store(r["id"]) for r in rows]


def update_store(store_id: str, **kwargs) -> bool:
    """更新店铺信息"""
    allowed = {"shop_name", "access_token", "refresh_token", "token_expires_at",
               "site_url", "default_brand",
               "default_currency", "status", "plan", "quota_total", "quota_used",
               "subscription_id", "billing_status"}
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    vals.append(store_id)
    with _conn() as c:
        c.execute(f"UPDATE stores SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()
    return True


# ─────────────────────────────────────────────
# Product CRUD
# ─────────────────────────────────────────────

def save_product(store_id: str, title: str, **kwargs) -> Product:
    """保存或更新产品（按 shopify_product_id 去重）"""
    pid = kwargs.get("id") or str(uuid.uuid4())
    shopify_pid = kwargs.get("shopify_product_id")

    with _conn() as c:
        # 检查是否已存在
        if shopify_pid:
            existing = c.execute(
                "SELECT id FROM products WHERE store_id = ? AND shopify_product_id = ?",
                (store_id, shopify_pid),
            ).fetchone()
            if existing:
                pid = existing["id"]

        c.execute(
            """INSERT OR REPLACE INTO products
               (id, store_id, shopify_product_id, handle, title, vendor, product_type,
                brand, material, gender, age_group, gpc_code, gpc_path, gpc_confidence,
                gpc_source, image_url, additional_images, description, optimized_title,
                cleaned_title, cleaned_description, feed_enabled, ai_status, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (pid, store_id, shopify_pid, kwargs.get("handle"), title,
             kwargs.get("vendor"), kwargs.get("product_type"),
             kwargs.get("brand"), kwargs.get("material"),
             kwargs.get("gender"), kwargs.get("age_group"),
             kwargs.get("gpc_code"), kwargs.get("gpc_path"),
             kwargs.get("gpc_confidence", 0), kwargs.get("gpc_source"),
             kwargs.get("image_url"), kwargs.get("additional_images"),
             kwargs.get("description"), kwargs.get("optimized_title"),
             kwargs.get("cleaned_title"), kwargs.get("cleaned_description"),
             kwargs.get("feed_enabled", 0), kwargs.get("ai_status", "raw"),
             kwargs.get("status", "active")),
        )
        c.commit()
    return get_product(pid)


def get_product(product_id: str) -> Optional[Product]:
    """获取产品信息"""
    with _conn() as c:
        row = c.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not row:
        return None
    return Product(**{k: row[k] for k in Product.__dataclass_fields__})


def get_store_products(store_id: str, status: str = "active") -> list[Product]:
    """获取店铺的所有产品"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM products WHERE store_id = ? AND status = ? ORDER BY title",
            (store_id, status),
        ).fetchall()
    return [Product(**{k: r[k] for k in Product.__dataclass_fields__}) for r in rows]


def get_store_product_by_shopify_id(
    store_id: str,
    shopify_product_id: str,
) -> Optional[Product]:
    """Lookup store product by Shopify numeric product id."""
    pid = str(shopify_product_id or "").strip()
    if not store_id or not pid:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM products WHERE store_id = ? AND shopify_product_id = ?",
            (store_id, pid),
        ).fetchone()
    if not row:
        return None
    return Product(**{k: row[k] for k in Product.__dataclass_fields__})


def update_product(product_id: str, **kwargs) -> bool:
    """Update product fields (catalog sync / soft-delete)."""
    allowed = {
        "title", "handle", "vendor", "product_type", "brand", "material",
        "gender", "age_group", "image_url", "additional_images", "description",
        "status", "feed_enabled", "ai_status", "shopify_product_id",
    }
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    vals.append(product_id)
    with _conn() as c:
        c.execute(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()
    return True


def update_product_gpc(product_id: str, gpc_code: str, gpc_path: str,
                       confidence: float = 1.0, source: str = "manual") -> bool:
    """更新产品的 GPC 分类（商家手动确认/修改）"""
    with _conn() as c:
        c.execute(
            """UPDATE products SET gpc_code=?, gpc_path=?, gpc_confidence=?,
               gpc_source=?, updated_at=datetime('now') WHERE id=?""",
            (gpc_code, gpc_path, confidence, source, product_id),
        )
        c.commit()
    return True


# ─────────────────────────────────────────────
# Variant CRUD
# ─────────────────────────────────────────────

def _variant_from_row(row) -> ProductVariant:
    keys = set(row.keys())
    data = {}
    for name, field in ProductVariant.__dataclass_fields__.items():
        if name in keys:
            data[name] = row[name]
        else:
            data[name] = field.default
    return ProductVariant(**data)


def save_variant(product_id: str, sku: str, **kwargs) -> ProductVariant:
    """Save/update a variant scoped to product_id (and shopify_variant_id when set).

    Do not match on global SKU alone — duplicate supplier SKUs across an active
    product and a draft copy would otherwise steal rows between products.
    """
    vid = kwargs.get("id") or str(uuid.uuid4())
    shopify_vid = str(kwargs.get("shopify_variant_id") or "").strip() or None

    with _conn() as c:
        existing = None
        if shopify_vid:
            existing = c.execute(
                """SELECT id, feed_image_url, feed_title FROM product_variants
                   WHERE product_id = ? AND shopify_variant_id = ?""",
                (product_id, shopify_vid),
            ).fetchone()
        if not existing and sku:
            existing = c.execute(
                """SELECT id, feed_image_url, feed_title FROM product_variants
                   WHERE product_id = ? AND sku = ?""",
                (product_id, sku),
            ).fetchone()
        if existing:
            vid = existing["id"]

        feed_image_url = kwargs.get("feed_image_url")
        if feed_image_url is None and existing:
            feed_image_url = existing["feed_image_url"] if "feed_image_url" in existing.keys() else None

        feed_title = kwargs.get("feed_title")
        if feed_title is None and existing and "feed_title" in existing.keys():
            feed_title = existing["feed_title"]

        c.execute(
            """INSERT OR REPLACE INTO product_variants
               (id, product_id, shopify_variant_id, sku, title, color, size,
                price, compare_at_price, inventory, weight, weight_unit,
                image_url, feed_image_url, feed_title, barcode, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (vid, product_id, shopify_vid, sku,
             kwargs.get("title"), kwargs.get("color"), kwargs.get("size"),
             kwargs.get("price", 0), kwargs.get("compare_at_price"),
             kwargs.get("inventory", 0), kwargs.get("weight"),
             kwargs.get("weight_unit", "kg"), kwargs.get("image_url"),
             feed_image_url, feed_title, kwargs.get("barcode"), kwargs.get("status", "active")),
        )
        c.commit()
    return get_variant(vid)


def get_variant(variant_id: str) -> Optional[ProductVariant]:
    """获取变体信息"""
    with _conn() as c:
        row = c.execute("SELECT * FROM product_variants WHERE id = ?", (variant_id,)).fetchone()
    if not row:
        return None
    return _variant_from_row(row)


def get_variant_by_sku_for_store(store_id: str, sku: str) -> Optional[ProductVariant]:
    """Fetch variant by SKU scoped to a store (join products)."""
    if not sku or not store_id:
        return None
    with _conn() as c:
        row = c.execute(
            """SELECT v.* FROM product_variants v
               JOIN products p ON p.id = v.product_id
               WHERE v.sku = ? AND p.store_id = ?
               LIMIT 1""",
            (sku, store_id),
        ).fetchone()
    if not row:
        return None
    return _variant_from_row(row)


def update_variant_attrs_for_store(
    store_id: str,
    sku: str,
    *,
    color: Optional[str] = None,
    size: Optional[str] = None,
) -> Optional[ProductVariant]:
    """Update color and/or size for a store-owned variant; preserve other columns."""
    if color is None and size is None:
        return get_variant_by_sku_for_store(store_id, sku)
    existing = get_variant_by_sku_for_store(store_id, sku)
    if not existing:
        return None
    return save_variant(
        existing.product_id,
        sku,
        id=existing.id,
        shopify_variant_id=existing.shopify_variant_id,
        title=existing.title,
        color=color if color is not None else existing.color,
        size=size if size is not None else existing.size,
        price=existing.price,
        compare_at_price=existing.compare_at_price,
        inventory=existing.inventory,
        weight=existing.weight,
        weight_unit=existing.weight_unit,
        image_url=existing.image_url,
        feed_image_url=existing.feed_image_url,
        feed_title=getattr(existing, "feed_title", None),
        barcode=existing.barcode,
        status=existing.status,
    )


def update_variant_feed_image_for_store(
    store_id: str,
    sku: str,
    image_url: str,
) -> Optional[ProductVariant]:
    """Set feed_image_url override for a store-owned variant."""
    existing = get_variant_by_sku_for_store(store_id, sku)
    if not existing:
        return None
    url = (image_url or "").strip()
    if not url.startswith("http"):
        return None
    return save_variant(
        existing.product_id,
        sku,
        id=existing.id,
        shopify_variant_id=existing.shopify_variant_id,
        title=existing.title,
        color=existing.color,
        size=existing.size,
        price=existing.price,
        compare_at_price=existing.compare_at_price,
        inventory=existing.inventory,
        weight=existing.weight,
        weight_unit=existing.weight_unit,
        image_url=existing.image_url,
        feed_image_url=url,
        feed_title=existing.feed_title,
        barcode=existing.barcode,
        status=existing.status,
    )


def update_variant_feed_title_for_store(
    store_id: str,
    sku: str,
    title: str,
) -> Optional[ProductVariant]:
    """Set per-SKU advertising title override (feed_title owner layer)."""
    existing = get_variant_by_sku_for_store(store_id, sku)
    if not existing:
        return None
    t = (title or "").strip()
    if not t:
        return None
    return save_variant(
        existing.product_id,
        sku,
        id=existing.id,
        shopify_variant_id=existing.shopify_variant_id,
        title=existing.title,
        color=existing.color,
        size=existing.size,
        price=existing.price,
        compare_at_price=existing.compare_at_price,
        inventory=existing.inventory,
        weight=existing.weight,
        weight_unit=existing.weight_unit,
        image_url=existing.image_url,
        feed_image_url=existing.feed_image_url,
        feed_title=t,
        barcode=existing.barcode,
        status=existing.status,
    )


def apply_feed_image_patches(store_id: str, patches: list[dict]) -> dict:
    """Apply [{sku, image_url}, ...] feed main-image overrides."""
    updated: list[str] = []
    missing: list[str] = []
    invalid: list[str] = []
    for item in patches or []:
        sku = (item.get("sku") or "").strip()
        image_url = (item.get("image_url") or "").strip()
        if not sku:
            continue
        if not image_url.startswith("http"):
            invalid.append(sku)
            continue
        result = update_variant_feed_image_for_store(store_id, sku, image_url)
        if result is None:
            missing.append(sku)
        else:
            updated.append(sku)
    return {"updated": updated, "missing": missing, "invalid": invalid}


def get_variant_by_sku_for_product(
    product_id: str,
    sku: str,
) -> Optional[ProductVariant]:
    if not product_id or not sku:
        return None
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM product_variants WHERE product_id = ? AND sku = ? LIMIT 1",
            (product_id, sku),
        ).fetchone()
    if not row:
        return None
    return _variant_from_row(row)


def apply_variant_attr_patches(
    store_id: str,
    patches: list[dict],
    *,
    shopify_product_id: Optional[str] = None,
) -> dict:
    """Apply [{sku, color?, size?}, ...] for one store. Returns updated/missing SKUs."""
    updated: list[str] = []
    missing: list[str] = []
    scoped_product = (
        get_store_product_by_shopify_id(store_id, shopify_product_id)
        if shopify_product_id
        else None
    )
    for item in patches or []:
        sku = (item.get("sku") or "").strip()
        if not sku:
            continue
        color = item.get("color")
        size = item.get("size")
        if color is not None:
            color = str(color).strip() or None
        if size is not None:
            size = str(size).strip() or None
        if color is None and size is None:
            continue
        result: Optional[ProductVariant] = None
        if scoped_product is not None:
            existing = get_variant_by_sku_for_product(scoped_product.id, sku)
            result = save_variant(
                scoped_product.id,
                sku,
                id=existing.id if existing else None,
                shopify_variant_id=existing.shopify_variant_id if existing else None,
                title=existing.title if existing else sku,
                color=color if color is not None else (existing.color if existing else ""),
                size=size if size is not None else (existing.size if existing else ""),
                price=existing.price if existing else 0,
                compare_at_price=existing.compare_at_price if existing else None,
                inventory=existing.inventory if existing else 0,
                weight=existing.weight if existing else None,
                weight_unit=existing.weight_unit if existing else None,
                image_url=existing.image_url if existing else None,
                feed_image_url=getattr(existing, "feed_image_url", None) if existing else None,
                feed_title=getattr(existing, "feed_title", None) if existing else None,
                barcode=existing.barcode if existing else None,
                status=existing.status if existing else "active",
            )
        else:
            result = update_variant_attrs_for_store(store_id, sku, color=color, size=size)
        if result is None:
            missing.append(sku)
        else:
            updated.append(sku)
    return {"updated": updated, "missing": missing}


def get_product_variants(product_id: str) -> list[ProductVariant]:
    """获取产品的所有变体"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM product_variants WHERE product_id = ? AND status = 'active' ORDER BY color, size",
            (product_id,),
        ).fetchall()
    return [_variant_from_row(r) for r in rows]


def bulk_save_variants(product_id: str, variants: list[dict]) -> int:
    """批量保存变体（用于 Shopify 同步后）"""
    count = 0
    for v in variants:
        save_variant(product_id, v["sku"], **v)
        count += 1
    return count


# ─────────────────────────────────────────────
# Feed Config CRUD
# ─────────────────────────────────────────────

def upsert_feed_config(store_id: str, country: str, **kwargs) -> FeedConfig:
    """创建或更新 Feed 配置（每店×每国唯一）"""
    fid = kwargs.get("id") or str(uuid.uuid4())

    with _conn() as c:
        # 检查是否已存在
        existing = c.execute(
            "SELECT id FROM feed_configs WHERE store_id = ? AND country = ?",
            (store_id, country),
        ).fetchone()
        if existing:
            fid = existing["id"]

        c.execute(
            """INSERT OR REPLACE INTO feed_configs
               (id, store_id, country, currency, language, site_link, auto_sync, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (fid, store_id, country, kwargs.get("currency", "USD"),
             kwargs.get("language", "en"), kwargs.get("site_link"),
             1 if kwargs.get("auto_sync", True) else 0,
             kwargs.get("status", "active")),
        )
        c.commit()
    return get_feed_config(fid)


def get_feed_config(config_id: str) -> Optional[FeedConfig]:
    """获取 Feed 配置"""
    with _conn() as c:
        row = c.execute("SELECT * FROM feed_configs WHERE id = ?", (config_id,)).fetchone()
    if not row:
        return None
    return FeedConfig(
        id=row["id"], store_id=row["store_id"], country=row["country"],
        currency=row["currency"], language=row["language"],
        site_link=row["site_link"], auto_sync=bool(row["auto_sync"]),
        last_synced_at=row["last_synced_at"], status=row["status"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def get_store_feed_configs(store_id: str) -> list[FeedConfig]:
    """获取店铺的所有 Feed 配置"""
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM feed_configs WHERE store_id = ? AND status = 'active'",
            (store_id,),
        ).fetchall()
    return [get_feed_config(r["id"]) for r in rows]


# ─────────────────────────────────────────────
# Feed File 记录
# ─────────────────────────────────────────────

def _row_to_feed_file(row) -> FeedFile:
    keys = row.keys() if hasattr(row, "keys") else []
    return FeedFile(
        id=row["id"], store_id=row["store_id"], country=row["country"],
        file_path=row["file_path"], feed_url=row["feed_url"],
        item_count=row["item_count"], file_size=row["file_size"],
        generated_at=row["generated_at"], status=row["status"],
        platform=row["platform"] if "platform" in keys and row["platform"] else "google",
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def get_feed_excluded_skus(
    store_id: str,
    country: str,
    platform: str = "google",
) -> set[str]:
    """SKUs the merchant removed from the durable feed (excluded on regen)."""
    init_store_schema()
    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    with _conn() as c:
        rows = c.execute(
            """SELECT sku FROM feed_excluded_skus
               WHERE store_id = ? AND platform = ? AND country = ?""",
            (store_id, plat, cu),
        ).fetchall()
    return {str(r["sku"]).strip() for r in rows if r["sku"]}


def add_feed_excluded_skus(
    store_id: str,
    skus: list[str],
    country: str,
    platform: str = "google",
) -> int:
    """Record SKUs removed from feed so regenerate does not add them back."""
    init_store_schema()
    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    now = datetime.now(timezone.utc).isoformat()
    added = 0
    with _conn() as c:
        for raw in skus or []:
            sku = str(raw or "").strip()
            if not sku:
                continue
            c.execute(
                """INSERT OR IGNORE INTO feed_excluded_skus
                   (store_id, platform, country, sku, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (store_id, plat, cu, sku, now),
            )
            if c.total_changes:
                added += 1
        c.commit()
    return added


def save_feed_file(store_id: str, country: str, file_path: str,
                   feed_url: str, item_count: int = 0,
                   platform: str = "google") -> FeedFile:
    """保存 Feed 文件记录（按 store × platform × country 覆盖最新）"""
    fid = str(uuid.uuid4())
    file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
    now = datetime.now(timezone.utc).isoformat()
    plat = (platform or "google").lower()
    cu = country.upper()

    with _conn() as c:
        # Soft-retire previous active row for same key
        c.execute(
            """UPDATE feed_files SET status='replaced', updated_at=datetime('now')
               WHERE store_id=? AND country=? AND IFNULL(platform,'google')=? AND status='active'""",
            (store_id, cu, plat),
        )
        c.execute(
            """INSERT INTO feed_files
               (id, store_id, country, platform, file_path, feed_url, item_count, file_size, generated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (fid, store_id, cu, plat, file_path, feed_url, item_count, file_size, now),
        )
        c.execute(
            """UPDATE feed_configs SET last_synced_at = ?, updated_at = datetime('now')
               WHERE store_id = ? AND country = ?""",
            (now, store_id, cu),
        )
        c.commit()
    return get_feed_file(fid)


def get_feed_file(file_id: str) -> Optional[FeedFile]:
    """获取 Feed 文件记录"""
    with _conn() as c:
        row = c.execute("SELECT * FROM feed_files WHERE id = ?", (file_id,)).fetchone()
    if not row:
        return None
    return _row_to_feed_file(row)


def get_store_feed(store_id: str, country: str, platform: str = "google") -> Optional[FeedFile]:
    """获取店铺某国某平台最新的 Feed 文件"""
    with _conn() as c:
        row = c.execute(
            """SELECT * FROM feed_files
               WHERE store_id = ? AND country = ? AND IFNULL(platform,'google') = ?
                 AND status = 'active'
               ORDER BY generated_at DESC LIMIT 1""",
            (store_id, country.upper(), (platform or "google").lower()),
        ).fetchone()
    if not row:
        return None
    return _row_to_feed_file(row)


def list_store_feeds(store_id: str) -> list[FeedFile]:
    """列出店铺所有 platform×country 最新 Feed"""
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM feed_files
               WHERE store_id = ? AND status = 'active'
               ORDER BY platform, country, generated_at DESC""",
            (store_id,),
        ).fetchall()
    seen = set()
    feeds = []
    for r in rows:
        plat = r["platform"] if "platform" in r.keys() and r["platform"] else "google"
        key = (plat, r["country"])
        if key not in seen:
            seen.add(key)
            feeds.append(_row_to_feed_file(r))
    return feeds


# ─────────────────────────────────────────────
# 批量操作（三段式流水线支持）
# ─────────────────────────────────────────────

def batch_set_feed_enabled(product_ids: list[str], enabled: bool = True) -> int:
    """批量设置产品是否进入 Feed"""
    if not product_ids:
        return 0
    placeholders = ",".join("?" for _ in product_ids)
    with _conn() as c:
        c.execute(
            f"UPDATE products SET feed_enabled = ?, updated_at = datetime('now') WHERE id IN ({placeholders})",
            [1 if enabled else 0] + product_ids,
        )
        c.commit()
    return len(product_ids)


def batch_set_ai_status(product_ids: list[str], ai_status: str) -> int:
    """批量更新 AI 处理状态"""
    if not product_ids:
        return 0
    placeholders = ",".join("?" for _ in product_ids)
    with _conn() as c:
        c.execute(
            f"UPDATE products SET ai_status = ?, updated_at = datetime('now') WHERE id IN ({placeholders})",
            [ai_status] + product_ids,
        )
        c.commit()
    return len(product_ids)


def update_product_ai_result(product_id: str, optimized_title: str,
                             gpc_code: str = None, gpc_path: str = None,
                             gpc_confidence: float = None, gpc_source: str = None,
                             cleaned_title: str = None, cleaned_description: str = None,
                             gender: str = None, age_group: str = None) -> bool:
    """更新单个产品的 AI 处理结果"""
    with _conn() as c:
        sets = ["ai_status = 'ready'", "updated_at = datetime('now')"]
        vals = []
        if optimized_title:
            sets.append("optimized_title = ?")
            vals.append(optimized_title)
        if gpc_code:
            sets.append("gpc_code = ?")
            vals.append(gpc_code)
        if gpc_path:
            sets.append("gpc_path = ?")
            vals.append(gpc_path)
        if gpc_confidence is not None:
            sets.append("gpc_confidence = ?")
            vals.append(gpc_confidence)
        if gpc_source:
            sets.append("gpc_source = ?")
            vals.append(gpc_source)
        if cleaned_title:
            sets.append("cleaned_title = ?")
            vals.append(cleaned_title)
        if cleaned_description:
            sets.append("cleaned_description = ?")
            vals.append(cleaned_description)
        if gender:
            sets.append("gender = ?")
            vals.append(gender)
        if age_group:
            sets.append("age_group = ?")
            vals.append(age_group)
        vals.append(product_id)
        c.execute(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()
    return True


def get_feed_products(store_id: str) -> list[Product]:
    """获取已启用 Feed 且 AI 处理就绪的产品"""
    with _conn() as c:
        rows = c.execute(
            """SELECT * FROM products
               WHERE store_id = ? AND feed_enabled = 1 AND ai_status = 'ready' AND status = 'active'
               ORDER BY title""",
            (store_id,),
        ).fetchall()
    return [Product(**{k: r[k] for k in Product.__dataclass_fields__}) for r in rows]


def get_store_products_by_status(store_id: str, ai_status: str = None) -> list[Product]:
    """按 AI 状态获取产品（用于前端展示）"""
    with _conn() as c:
        if ai_status:
            rows = c.execute(
                "SELECT * FROM products WHERE store_id = ? AND ai_status = ? AND status = 'active' ORDER BY title",
                (store_id, ai_status),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM products WHERE store_id = ? AND status = 'active' ORDER BY title",
                (store_id,),
            ).fetchall()
    return [Product(**{k: r[k] for k in Product.__dataclass_fields__}) for r in rows]


def get_store_dashboard(store_id: str) -> dict:
    """获取店铺仪表盘数据（前端展示用）"""
    with _conn() as c:
        total = c.execute(
            "SELECT COUNT(*) FROM products WHERE store_id = ? AND status = 'active'",
            (store_id,),
        ).fetchone()[0]
        raw = c.execute(
            "SELECT COUNT(*) FROM products WHERE store_id = ? AND ai_status = 'raw' AND status = 'active'",
            (store_id,),
        ).fetchone()[0]
        ready = c.execute(
            "SELECT COUNT(*) FROM products WHERE store_id = ? AND ai_status = 'ready' AND status = 'active'",
            (store_id,),
        ).fetchone()[0]
        feed_enabled = c.execute(
            "SELECT COUNT(*) FROM products WHERE store_id = ? AND feed_enabled = 1 AND status = 'active'",
            (store_id,),
        ).fetchone()[0]

    return {
        "store_id": store_id,
        "total_products": total,
        "ai_raw": raw,
        "ai_ready": ready,
        "feed_enabled": feed_enabled,
    }


# ─────────────────────────────────────────────
# 统计
# ─────────────────────────────────────────────

def get_store_stats(store_id: str) -> dict:
    """获取店铺统计信息"""
    with _conn() as c:
        products = c.execute(
            "SELECT COUNT(*) FROM products WHERE store_id = ? AND status = 'active'",
            (store_id,),
        ).fetchone()[0]
        variants = c.execute(
            """SELECT COUNT(*) FROM product_variants pv
               JOIN products p ON pv.product_id = p.id
               WHERE p.store_id = ? AND pv.status = 'active'""",
            (store_id,),
        ).fetchone()[0]
        feeds = c.execute(
            "SELECT COUNT(DISTINCT country) FROM feed_files WHERE store_id = ? AND status = 'active'",
            (store_id,),
        ).fetchone()[0]

    return {
        "store_id": store_id,
        "active_products": products,
        "active_variants": variants,
        "feed_countries": feeds,
    }


# ─────────────────────────────────────────────
# Product Assets / Usage / Store Jobs
# ─────────────────────────────────────────────

def upsert_product_asset(store_id: str, product_id: str, platform: str, language: str,
                         title: str = "", description: str = "",
                         tags: list = None) -> ProductAsset:
    """写入或更新 product_assets（product_id + platform + language 唯一）"""
    tags_json = json.dumps(tags or [], ensure_ascii=False)
    with _conn() as c:
        existing = c.execute(
            """SELECT id FROM product_assets
               WHERE product_id = ? AND platform = ? AND language = ?""",
            (product_id, platform.lower(), language.upper()),
        ).fetchone()
        if existing:
            aid = existing["id"]
            c.execute(
                """UPDATE product_assets
                   SET title=?, description=?, tags_json=?, updated_at=datetime('now')
                   WHERE id=?""",
                (title, description, tags_json, aid),
            )
        else:
            aid = str(uuid.uuid4())
            c.execute(
                """INSERT INTO product_assets
                   (id, store_id, product_id, platform, language, title, description, tags_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (aid, store_id, product_id, platform.lower(), language.upper(),
                 title, description, tags_json),
            )
        c.commit()
    return get_product_asset(aid)


def get_product_asset(asset_id: str) -> Optional[ProductAsset]:
    with _conn() as c:
        row = c.execute("SELECT * FROM product_assets WHERE id = ?", (asset_id,)).fetchone()
    if not row:
        return None
    return ProductAsset(
        id=row["id"], store_id=row["store_id"], product_id=row["product_id"],
        platform=row["platform"], language=row["language"],
        title=row["title"], description=row["description"], tags_json=row["tags_json"],
        updated_at=row["updated_at"], created_at=row["created_at"],
    )


def get_product_asset_by_key(product_id: str, platform: str, language: str) -> Optional[ProductAsset]:
    with _conn() as c:
        row = c.execute(
            """SELECT * FROM product_assets
               WHERE product_id = ? AND platform = ? AND language = ?""",
            (product_id, platform.lower(), language.upper()),
        ).fetchone()
    if not row:
        return None
    return get_product_asset(row["id"])


def record_usage(store_id: str, platform: str, language: str,
                 job_id: str = None, sku: str = None) -> str:
    """记录一条配额消耗，并 +1 stores.quota_used"""
    lid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            """INSERT INTO usage_ledger (id, store_id, job_id, sku, platform, language)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lid, store_id, job_id, sku, platform.lower(), language.upper()),
        )
        c.execute(
            """UPDATE stores SET quota_used = quota_used + 1, updated_at=datetime('now')
               WHERE id = ?""",
            (store_id,),
        )
        c.commit()
    return lid


def create_store_job(store_id: str, platforms: list, languages: list,
                     product_ids: list, total_units: int = 0) -> StoreJob:
    jid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            """INSERT INTO store_jobs
               (id, store_id, status, platforms, languages, product_ids, total_units)
               VALUES (?, ?, 'pending', ?, ?, ?, ?)""",
            (jid, store_id, json.dumps(platforms), json.dumps(languages),
             json.dumps(product_ids), total_units),
        )
        c.commit()
    return get_store_job(jid)


def get_store_job(job_id: str) -> Optional[StoreJob]:
    with _conn() as c:
        row = c.execute("SELECT * FROM store_jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    return StoreJob(
        id=row["id"], store_id=row["store_id"], status=row["status"],
        platforms=row["platforms"], languages=row["languages"],
        product_ids=row["product_ids"], total_units=row["total_units"],
        done_units=row["done_units"], ok_units=row["ok_units"],
        fail_units=row["fail_units"], result_json=row["result_json"],
        error_msg=row["error_msg"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def get_latest_completed_store_job(store_id: str) -> Optional[StoreJob]:
    """Most recent successful generate job for App Home KPI reload."""
    with _conn() as c:
        row = c.execute(
            """SELECT * FROM store_jobs
               WHERE store_id = ? AND status = 'completed'
               ORDER BY updated_at DESC LIMIT 1""",
            (store_id,),
        ).fetchone()
    if not row:
        return None
    return StoreJob(
        id=row["id"], store_id=row["store_id"], status=row["status"],
        platforms=row["platforms"], languages=row["languages"],
        product_ids=row["product_ids"], total_units=row["total_units"],
        done_units=row["done_units"], ok_units=row["ok_units"],
        fail_units=row["fail_units"], result_json=row["result_json"],
        error_msg=row["error_msg"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def update_store_job(job_id: str, **kwargs) -> bool:
    allowed = {"status", "total_units", "done_units", "ok_units", "fail_units",
               "result_json", "error_msg", "platforms", "languages", "product_ids"}
    sets, vals = [], []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return False
    sets.append("updated_at = datetime('now')")
    vals.append(job_id)
    with _conn() as c:
        c.execute(f"UPDATE store_jobs SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()
    return True


def purge_store_data(store_id: str) -> bool:
    """Hard-delete one shop's catalog, jobs, feeds, and store row (shop/redact)."""
    import shutil

    if not store_id:
        return False
    store = get_store(store_id)
    if not store:
        return False

    feed_paths: list[str] = []
    with _conn() as c:
        rows = c.execute(
            "SELECT file_path FROM feed_files WHERE store_id = ?",
            (store_id,),
        ).fetchall()
        feed_paths = [r["file_path"] for r in rows if r["file_path"]]
        c.execute(
            """DELETE FROM product_variants WHERE product_id IN
               (SELECT id FROM products WHERE store_id = ?)""",
            (store_id,),
        )
        c.execute("DELETE FROM product_assets WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM usage_ledger WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM store_jobs WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM feed_files WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM feed_excluded_skus WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM feed_configs WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM products WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM gmc_product_issues WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM google_merchant_accounts WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM google_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM ads_metrics_daily WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM meta_catalogs WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM meta_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM meta_product_issues WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM tiktok_shops WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM tiktok_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM tiktok_product_issues WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM stores WHERE id = ?", (store_id,))
        c.commit()

    for p in feed_paths:
        try:
            Path(p).unlink(missing_ok=True)
        except OSError:
            pass
        parent = Path(p).parent
        if parent.exists():
            try:
                if not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass

    try:
        from .config import FEEDS_DIR
        shutil.rmtree(FEEDS_DIR / store_id, ignore_errors=True)
    except Exception:
        pass
    shutil.rmtree(DATA_DIR / "processed_images" / store_id, ignore_errors=True)
    return True


# ─────────────────────────────────────────────
# Google OAuth / GMC issues / Ads metrics
# ─────────────────────────────────────────────

def upsert_google_oauth_token(store_id: str, refresh_token_enc: str, scopes: str) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO google_oauth_tokens (store_id, refresh_token_enc, scopes, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(store_id) DO UPDATE SET
              refresh_token_enc = excluded.refresh_token_enc,
              scopes = excluded.scopes,
              updated_at = datetime('now')
            """,
            (store_id, refresh_token_enc, scopes or ""),
        )
        c.commit()


def get_google_oauth_token(store_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM google_oauth_tokens WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_google_oauth_token(store_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM google_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM google_merchant_accounts WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM gmc_product_issues WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM ads_metrics_daily WHERE store_id = ?", (store_id,))
        c.commit()


def upsert_google_merchant_account(
    store_id: str,
    merchant_id: str,
    display_name: str = "",
    *,
    select: bool = False,
) -> dict:
    mid = str(merchant_id).strip()
    row_id = f"{store_id}:{mid}"
    with _conn() as c:
        if select:
            c.execute(
                "UPDATE google_merchant_accounts SET is_selected = 0 WHERE store_id = ?",
                (store_id,),
            )
        c.execute(
            """
            INSERT INTO google_merchant_accounts
              (id, store_id, merchant_id, display_name, is_selected, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(store_id, merchant_id) DO UPDATE SET
              display_name = excluded.display_name,
              is_selected = CASE WHEN ? THEN 1 ELSE google_merchant_accounts.is_selected END
            """,
            (row_id, store_id, mid, display_name or mid, 1 if select else 0, 1 if select else 0),
        )
        c.commit()
        row = c.execute(
            "SELECT * FROM google_merchant_accounts WHERE store_id = ? AND merchant_id = ?",
            (store_id, mid),
        ).fetchone()
        return dict(row)


def list_google_merchant_accounts(store_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM google_merchant_accounts
            WHERE store_id = ?
            ORDER BY is_selected DESC, created_at ASC
            """,
            (store_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_selected_merchant_id(store_id: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            """
            SELECT merchant_id FROM google_merchant_accounts
            WHERE store_id = ? AND is_selected = 1
            LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        if row:
            return row["merchant_id"]
        row = c.execute(
            """
            SELECT merchant_id FROM google_merchant_accounts
            WHERE store_id = ? ORDER BY created_at ASC LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        return row["merchant_id"] if row else None


def replace_gmc_product_issues(store_id: str, merchant_id: str, issues: list[dict]) -> int:
    """Replace all cached issues for one merchant. issues keys: offer_id, status, reason_code, reason_text, product_id_internal, raw_json."""
    mid = str(merchant_id).strip()
    with _conn() as c:
        c.execute(
            "DELETE FROM gmc_product_issues WHERE store_id = ? AND merchant_id = ?",
            (store_id, mid),
        )
        n = 0
        for it in issues:
            oid = str(it.get("offer_id") or "").strip()
            if not oid:
                continue
            c.execute(
                """
                INSERT INTO gmc_product_issues
                  (id, store_id, merchant_id, offer_id, product_id_internal,
                   status, reason_code, reason_text, raw_json, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    str(uuid.uuid4()),
                    store_id,
                    mid,
                    oid,
                    it.get("product_id_internal"),
                    str(it.get("status") or ""),
                    str(it.get("reason_code") or ""),
                    str(it.get("reason_text") or ""),
                    it.get("raw_json"),
                ),
            )
            n += 1
        c.commit()
        return n


def list_gmc_product_issues(store_id: str, merchant_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM gmc_product_issues
            WHERE store_id = ? AND merchant_id = ?
            ORDER BY
              CASE WHEN product_id_internal IS NULL OR product_id_internal = '' THEN 1 ELSE 0 END,
              status, offer_id
            """,
            (store_id, merchant_id),
        ).fetchall()
        return [dict(r) for r in rows]


def replace_ads_metrics_daily(store_id: str, ads_customer_id: str, rows: list[dict]) -> int:
    cid = str(ads_customer_id).strip()
    with _conn() as c:
        c.execute(
            "DELETE FROM ads_metrics_daily WHERE store_id = ? AND ads_customer_id = ?",
            (store_id, cid),
        )
        n = 0
        for it in rows:
            c.execute(
                """
                INSERT INTO ads_metrics_daily
                  (id, store_id, ads_customer_id, date, offer_id, campaign_id,
                   impressions, clicks, cost_micros, conversions, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    str(uuid.uuid4()),
                    store_id,
                    cid,
                    str(it.get("date") or ""),
                    it.get("offer_id"),
                    it.get("campaign_id"),
                    int(it.get("impressions") or 0),
                    int(it.get("clicks") or 0),
                    int(it.get("cost_micros") or 0),
                    float(it.get("conversions") or 0),
                ),
            )
            n += 1
        c.commit()
        return n


def list_ads_metrics_daily(
    store_id: str,
    ads_customer_id: str,
    *,
    product_level_only: bool = False,
) -> list[dict]:
    with _conn() as c:
        if product_level_only:
            rows = c.execute(
                """
                SELECT * FROM ads_metrics_daily
                WHERE store_id = ? AND ads_customer_id = ?
                  AND offer_id IS NOT NULL AND offer_id != ''
                ORDER BY date DESC, clicks DESC
                """,
                (store_id, ads_customer_id),
            ).fetchall()
        else:
            rows = c.execute(
                """
                SELECT * FROM ads_metrics_daily
                WHERE store_id = ? AND ads_customer_id = ?
                ORDER BY date DESC, clicks DESC
                """,
                (store_id, ads_customer_id),
            ).fetchall()
        return [dict(r) for r in rows]


def list_store_skus(store_id: str) -> set[str]:
    """SKU set for offer_id matching (feed g:id)."""
    with _conn() as c:
        rows = c.execute(
            """
            SELECT v.sku FROM product_variants v
            JOIN products p ON p.id = v.product_id
            WHERE p.store_id = ? AND v.sku IS NOT NULL AND v.sku != ''
            """,
            (store_id,),
        ).fetchall()
        return {str(r["sku"]) for r in rows}


# ─────────────────────────────────────────────
# Meta OAuth / catalogs
# ─────────────────────────────────────────────

def upsert_meta_oauth_token(store_id: str, access_token_enc: str, scopes: str) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO meta_oauth_tokens (store_id, access_token_enc, scopes, updated_at)
            VALUES (?, ?, ?, datetime('now'))
            ON CONFLICT(store_id) DO UPDATE SET
              access_token_enc = excluded.access_token_enc,
              scopes = excluded.scopes,
              updated_at = datetime('now')
            """,
            (store_id, access_token_enc, scopes or ""),
        )
        c.commit()


def get_meta_oauth_token(store_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM meta_oauth_tokens WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_meta_oauth_token(store_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM meta_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM meta_catalogs WHERE store_id = ?", (store_id,))
        c.commit()


def upsert_meta_catalog(
    store_id: str,
    catalog_id: str,
    display_name: str = "",
    *,
    product_feed_id: str = "",
    select: bool = False,
) -> dict:
    cid = str(catalog_id).strip()
    row_id = f"{store_id}:meta:{cid}"
    with _conn() as c:
        if select:
            c.execute(
                "UPDATE meta_catalogs SET is_selected = 0 WHERE store_id = ?",
                (store_id,),
            )
        existing = c.execute(
            "SELECT product_feed_id FROM meta_catalogs WHERE store_id = ? AND catalog_id = ?",
            (store_id, cid),
        ).fetchone()
        feed_id = product_feed_id or (
            (existing["product_feed_id"] if existing else "") or ""
        )
        c.execute(
            """
            INSERT INTO meta_catalogs
              (id, store_id, catalog_id, display_name, product_feed_id, is_selected, created_at)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(store_id, catalog_id) DO UPDATE SET
              display_name = excluded.display_name,
              product_feed_id = CASE
                WHEN excluded.product_feed_id != '' THEN excluded.product_feed_id
                ELSE meta_catalogs.product_feed_id
              END,
              is_selected = CASE WHEN ? THEN 1 ELSE meta_catalogs.is_selected END
            """,
            (
                row_id,
                store_id,
                cid,
                display_name or cid,
                feed_id,
                1 if select else 0,
                1 if select else 0,
            ),
        )
        c.commit()
        row = c.execute(
            "SELECT * FROM meta_catalogs WHERE store_id = ? AND catalog_id = ?",
            (store_id, cid),
        ).fetchone()
        return dict(row)


def list_meta_catalogs(store_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM meta_catalogs
            WHERE store_id = ?
            ORDER BY is_selected DESC, created_at ASC
            """,
            (store_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_selected_meta_catalog_id(store_id: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            """
            SELECT catalog_id FROM meta_catalogs
            WHERE store_id = ? AND is_selected = 1
            LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        if row:
            return row["catalog_id"]
        row = c.execute(
            """
            SELECT catalog_id FROM meta_catalogs
            WHERE store_id = ? ORDER BY created_at ASC LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        return row["catalog_id"] if row else None


# ─────────────────────────────────────────────
# TikTok OAuth / shops
# ─────────────────────────────────────────────

def upsert_tiktok_oauth_token(
    store_id: str,
    refresh_token_enc: str,
    access_token_enc: str = "",
    scopes: str = "",
) -> None:
    with _conn() as c:
        c.execute(
            """
            INSERT INTO tiktok_oauth_tokens
              (store_id, refresh_token_enc, access_token_enc, scopes, updated_at)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(store_id) DO UPDATE SET
              refresh_token_enc = excluded.refresh_token_enc,
              access_token_enc = excluded.access_token_enc,
              scopes = excluded.scopes,
              updated_at = datetime('now')
            """,
            (store_id, refresh_token_enc, access_token_enc or "", scopes or ""),
        )
        c.commit()


def get_tiktok_oauth_token(store_id: str) -> Optional[dict]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM tiktok_oauth_tokens WHERE store_id = ?",
            (store_id,),
        ).fetchone()
        return dict(row) if row else None


def delete_tiktok_oauth_token(store_id: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM tiktok_oauth_tokens WHERE store_id = ?", (store_id,))
        c.execute("DELETE FROM tiktok_shops WHERE store_id = ?", (store_id,))
        c.commit()


def upsert_tiktok_shop(
    store_id: str,
    shop_id: str,
    display_name: str = "",
    *,
    feed_url: str = "",
    cipher: str = "",
    select: bool = False,
) -> dict:
    sid = str(shop_id).strip()
    row_id = f"{store_id}:tt:{sid}"
    with _conn() as c:
        if select:
            c.execute(
                "UPDATE tiktok_shops SET is_selected = 0 WHERE store_id = ?",
                (store_id,),
            )
        existing = c.execute(
            "SELECT feed_url, cipher FROM tiktok_shops WHERE store_id = ? AND shop_id = ?",
            (store_id, sid),
        ).fetchone()
        keep_feed = feed_url or ((existing["feed_url"] if existing else "") or "")
        keep_cipher = cipher or ((existing["cipher"] if existing else "") or "")
        c.execute(
            """
            INSERT INTO tiktok_shops
              (id, store_id, shop_id, display_name, feed_url, cipher, is_selected, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(store_id, shop_id) DO UPDATE SET
              display_name = excluded.display_name,
              feed_url = CASE
                WHEN excluded.feed_url != '' THEN excluded.feed_url
                ELSE tiktok_shops.feed_url
              END,
              cipher = CASE
                WHEN excluded.cipher != '' THEN excluded.cipher
                ELSE tiktok_shops.cipher
              END,
              is_selected = CASE WHEN ? THEN 1 ELSE tiktok_shops.is_selected END
            """,
            (
                row_id,
                store_id,
                sid,
                display_name or sid,
                keep_feed,
                keep_cipher,
                1 if select else 0,
                1 if select else 0,
            ),
        )
        c.commit()
        row = c.execute(
            "SELECT * FROM tiktok_shops WHERE store_id = ? AND shop_id = ?",
            (store_id, sid),
        ).fetchone()
        return dict(row)


def list_tiktok_shops(store_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM tiktok_shops
            WHERE store_id = ?
            ORDER BY is_selected DESC, created_at ASC
            """,
            (store_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def get_selected_tiktok_shop_id(store_id: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            """
            SELECT shop_id FROM tiktok_shops
            WHERE store_id = ? AND is_selected = 1
            LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        if row:
            return row["shop_id"]
        row = c.execute(
            """
            SELECT shop_id FROM tiktok_shops
            WHERE store_id = ? ORDER BY created_at ASC LIMIT 1
            """,
            (store_id,),
        ).fetchone()
        return row["shop_id"] if row else None


def replace_meta_product_issues(store_id: str, catalog_id: str, issues: list[dict]) -> int:
    cid = str(catalog_id).strip()
    with _conn() as c:
        c.execute(
            "DELETE FROM meta_product_issues WHERE store_id = ? AND catalog_id = ?",
            (store_id, cid),
        )
        n = 0
        for it in issues:
            oid = str(it.get("offer_id") or "").strip()
            if not oid:
                continue
            c.execute(
                """
                INSERT INTO meta_product_issues
                  (id, store_id, catalog_id, offer_id, product_id_internal,
                   status, reason_code, reason_text, raw_json, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    str(uuid.uuid4()),
                    store_id,
                    cid,
                    oid,
                    it.get("product_id_internal"),
                    str(it.get("status") or ""),
                    str(it.get("reason_code") or ""),
                    str(it.get("reason_text") or ""),
                    it.get("raw_json"),
                ),
            )
            n += 1
        c.commit()
        return n


def list_meta_product_issues(store_id: str, catalog_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM meta_product_issues
            WHERE store_id = ? AND catalog_id = ?
            ORDER BY
              CASE WHEN product_id_internal IS NULL OR product_id_internal = '' THEN 1 ELSE 0 END,
              status, offer_id
            """,
            (store_id, catalog_id),
        ).fetchall()
        return [dict(r) for r in rows]


def replace_tiktok_product_issues(store_id: str, shop_id: str, issues: list[dict]) -> int:
    sid = str(shop_id).strip()
    with _conn() as c:
        c.execute(
            "DELETE FROM tiktok_product_issues WHERE store_id = ? AND shop_id = ?",
            (store_id, sid),
        )
        n = 0
        for it in issues:
            oid = str(it.get("offer_id") or "").strip()
            if not oid:
                continue
            c.execute(
                """
                INSERT INTO tiktok_product_issues
                  (id, store_id, shop_id, offer_id, product_id_internal,
                   status, reason_code, reason_text, raw_json, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    str(uuid.uuid4()),
                    store_id,
                    sid,
                    oid,
                    it.get("product_id_internal"),
                    str(it.get("status") or ""),
                    str(it.get("reason_code") or ""),
                    str(it.get("reason_text") or ""),
                    it.get("raw_json"),
                ),
            )
            n += 1
        c.commit()
        return n


def list_tiktok_product_issues(store_id: str, shop_id: str) -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            """
            SELECT * FROM tiktok_product_issues
            WHERE store_id = ? AND shop_id = ?
            ORDER BY
              CASE WHEN product_id_internal IS NULL OR product_id_internal = '' THEN 1 ELSE 0 END,
              status, offer_id
            """,
            (store_id, shop_id),
        ).fetchall()
        return [dict(r) for r in rows]


# ─────────────────────────────────────────────
# 初始化
# ─────────────────────────────────────────────

init_store_schema()
