"""数据库层 — 用户、任务、Magic Link（SQLite）"""
import sqlite3, os, uuid, secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

DATA_DIR = Path(os.getenv("ADFEED_DATA_DIR", Path(__file__).resolve().parent.parent / "data"))
DB_PATH = DATA_DIR / "webapp.db"

DATA_DIR.mkdir(parents=True, exist_ok=True)


@contextmanager
def _conn():
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
    finally:
        c.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    google_id     TEXT UNIQUE,
    name          TEXT,
    avatar_url    TEXT,
    plan          TEXT DEFAULT 'free',
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    quota_total   INTEGER DEFAULT 20,
    quota_used    INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS magic_links (
    id            TEXT PRIMARY KEY,
    email         TEXT NOT NULL,
    token         TEXT UNIQUE NOT NULL,
    expires_at    TEXT NOT NULL,
    used          INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS jobs (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    filename      TEXT NOT NULL,
    file_hash     TEXT,
    country_mask  TEXT NOT NULL DEFAULT '["US"]',
    status        TEXT DEFAULT 'analyzing',
    total_rows    INTEGER DEFAULT 0,
    preview_json  TEXT,
    done_rows     INTEGER DEFAULT 0,
    ok_rows       INTEGER DEFAULT 0,
    fail_rows     INTEGER DEFAULT 0,
    truncated     INTEGER DEFAULT 0,
    result_csv    TEXT,
    error_msg     TEXT,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS shopify_connections (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id),
    shop_domain   TEXT UNIQUE NOT NULL,
    shop_name     TEXT,
    access_token  TEXT NOT NULL,
    scope         TEXT DEFAULT 'read_products',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_user ON jobs(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_magic_links_token ON magic_links(token);
CREATE INDEX IF NOT EXISTS idx_users_google ON users(google_id);
CREATE INDEX IF NOT EXISTS idx_shopify_user ON shopify_connections(user_id);
"""


def init_db():
    with _conn() as c:
        c.executescript(SCHEMA)
        c.commit()


@dataclass
class User:
    id: str
    email: str
    google_id: Optional[str] = None
    name: Optional[str] = None
    avatar_url: Optional[str] = None
    plan: str = "free"
    quota_total: int = 20
    quota_used: int = 0
    stripe_customer_id: Optional[str] = None
    stripe_subscription_id: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def quota_remaining(self) -> int:
        return max(0, self.quota_total - self.quota_used)


@dataclass
class Job:
    id: str
    user_id: str
    filename: str
    file_hash: Optional[str] = None
    country_mask: str = '["US"]'
    status: str = "analyzing"
    total_rows: int = 0
    preview_json: Optional[str] = None
    done_rows: int = 0
    ok_rows: int = 0
    fail_rows: int = 0
    truncated: bool = False
    result_csv: Optional[str] = None
    error_msg: Optional[str] = None
    created_at: str = ""
    updated_at: str = ""

    @property
    def progress_pct(self) -> int:
        if self.total_rows == 0:
            return 0
        return min(100, int(100 * self.done_rows / self.total_rows))


# ── User CRUD ──

def create_user(email: str, google_id: str = None, name: str = None, avatar_url: str = None) -> User:
    uid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            "INSERT INTO users (id, email, google_id, name, avatar_url) VALUES (?,?,?,?,?)",
            (uid, email, google_id, name, avatar_url),
        )
        c.commit()
    return get_user(uid)


def get_user(user_id: str) -> Optional[User]:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_email(email: str) -> Optional[User]:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return _row_to_user(row) if row else None


def get_user_by_google_id(google_id: str) -> Optional[User]:
    with _conn() as c:
        row = c.execute("SELECT * FROM users WHERE google_id = ?", (google_id,)).fetchone()
    return _row_to_user(row) if row else None


def update_user(user_id: str, **kwargs):
    allowed = {"name", "avatar_url", "plan", "quota_total", "quota_used",
               "stripe_customer_id", "stripe_subscription_id"}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            vals.append(v)
    if not sets:
        return
    sets.append("updated_at = datetime('now')")
    vals.append(user_id)
    with _conn() as c:
        c.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()


def increment_quota(user_id: str, count: int):
    with _conn() as c:
        c.execute(
            "UPDATE users SET quota_used = quota_used + ?, updated_at = datetime('now') WHERE id = ?",
            (count, user_id),
        )
        c.commit()


def _row_to_user(r) -> User:
    return User(
        id=r["id"], email=r["email"], google_id=r["google_id"],
        name=r["name"], avatar_url=r["avatar_url"],
        plan=r["plan"], quota_total=r["quota_total"], quota_used=r["quota_used"],
        stripe_customer_id=r["stripe_customer_id"],
        stripe_subscription_id=r["stripe_subscription_id"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


# ── Magic Link ──

def create_magic_link(email: str, ttl_minutes: int = 15) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()
    with _conn() as c:
        c.execute(
            "INSERT INTO magic_links (id, email, token, expires_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), email, token, expires),
        )
        c.commit()
    return token


def verify_magic_link(token: str) -> Optional[str]:
    with _conn() as c:
        row = c.execute(
            "SELECT * FROM magic_links WHERE token = ? AND used = 0 AND expires_at > datetime('now')",
            (token,),
        ).fetchone()
        if not row:
            return None
        c.execute("UPDATE magic_links SET used = 1 WHERE id = ?", (row["id"],))
        c.commit()
        return row["email"]


# ── Job CRUD ──

def create_job(user_id: str, filename: str, country_mask: str = '["US"]', file_hash: str = None) -> Job:
    jid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs (id, user_id, filename, country_mask, file_hash) VALUES (?,?,?,?,?)",
            (jid, user_id, filename, country_mask, file_hash),
        )
        c.commit()
    return get_job(jid)


def get_job(job_id: str) -> Optional[Job]:
    with _conn() as c:
        row = c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_job(row) if row else None


def list_jobs(user_id: str, limit: int = 20) -> list[Job]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
    return [_row_to_job(r) for r in rows]


def update_job(job_id: str, **kwargs):
    allowed = {"status", "total_rows", "preview_json", "done_rows", "ok_rows", "fail_rows",
               "truncated", "result_csv", "error_msg"}
    sets = []
    vals = []
    for k, v in kwargs.items():
        if k in allowed:
            sets.append(f"{k} = ?")
            if k == "truncated":
                vals.append(1 if v else 0)
            else:
                vals.append(v)
    if not sets:
        return
    sets.append("updated_at = datetime('now')")
    vals.append(job_id)
    with _conn() as c:
        c.execute(f"UPDATE jobs SET {', '.join(sets)} WHERE id = ?", vals)
        c.commit()


def _row_to_job(r) -> Job:
    return Job(
        id=r["id"], user_id=r["user_id"], filename=r["filename"],
        file_hash=r["file_hash"], country_mask=r["country_mask"],
        status=r["status"], total_rows=r["total_rows"],
        preview_json=r["preview_json"],
        done_rows=r["done_rows"], ok_rows=r["ok_rows"],
        fail_rows=r["fail_rows"], truncated=bool(r["truncated"]),
        result_csv=r["result_csv"],
        error_msg=r["error_msg"],
        created_at=r["created_at"], updated_at=r["updated_at"],
    )


init_db()


# ── Shopify Connection CRUD ──

@dataclass
class ShopifyConnection:
    id: str
    user_id: str
    shop_domain: str
    shop_name: Optional[str] = None
    access_token: str = ""
    scope: str = "read_products"
    created_at: str = ""
    updated_at: str = ""


def create_shopify_connection(user_id: str, shop_domain: str, shop_name: str, access_token: str) -> ShopifyConnection:
    cid = str(uuid.uuid4())
    with _conn() as c:
        # 同一用户只保留一个连接（覆盖旧的）
        c.execute("DELETE FROM shopify_connections WHERE user_id = ?", (user_id,))
        c.execute(
            "INSERT INTO shopify_connections (id, user_id, shop_domain, shop_name, access_token) VALUES (?,?,?,?,?)",
            (cid, user_id, shop_domain, shop_name, access_token),
        )
        c.commit()
    return get_shopify_connection(user_id)


def get_shopify_connection(user_id: str) -> Optional[ShopifyConnection]:
    with _conn() as c:
        row = c.execute("SELECT * FROM shopify_connections WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return ShopifyConnection(
        id=row["id"], user_id=row["user_id"], shop_domain=row["shop_domain"],
        shop_name=row["shop_name"], access_token=row["access_token"],
        scope=row["scope"], created_at=row["created_at"], updated_at=row["updated_at"],
    )


def delete_shopify_connection(user_id: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM shopify_connections WHERE user_id = ?", (user_id,))
        c.commit()
        return cur.rowcount > 0
