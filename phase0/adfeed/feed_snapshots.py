"""Feed file snapshots: keep last N before overwrite; restore to current URL."""
from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from . import store_db
from .config import FEEDS_DIR, PUBLIC_BASE_URL
from .db import _conn
from .multi_platform_feeds import durable_feed_path, durable_feed_url

SNAPSHOT_KEEP = 5


def _snapshots_dir(store_id: str, platform: str) -> Path:
    return FEEDS_DIR / store_id / (platform or "google").lower() / "_snapshots"


def init_snapshot_schema() -> None:
    store_db.init_store_schema()
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS feed_snapshots (
                id TEXT PRIMARY KEY,
                store_id TEXT NOT NULL,
                platform TEXT NOT NULL DEFAULT 'google',
                country TEXT NOT NULL,
                file_path TEXT NOT NULL,
                item_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                job_id TEXT
            )"""
        )
        c.execute(
            """CREATE INDEX IF NOT EXISTS idx_feed_snapshots_store
               ON feed_snapshots(store_id, platform, country, created_at DESC)"""
        )
        c.commit()


def maybe_snapshot_current(
    store_id: str,
    platform: str,
    country: str,
    current_path: Path,
    *,
    job_id: Optional[str] = None,
) -> Optional[str]:
    """Copy existing current feed to _snapshots before overwrite. Returns snapshot id."""
    init_snapshot_schema()
    path = Path(current_path)
    if not path.exists() or path.stat().st_size <= 0:
        return None

    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    lang = cu.lower()
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = _snapshots_dir(store_id, plat)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"{ts}_{uuid.uuid4().hex[:8]}_{lang}{path.suffix or '.xml'}"
    shutil.copy2(path, dest)

    # Count items cheaply
    item_count = 0
    try:
        text = dest.read_text(encoding="utf-8", errors="replace")
        if dest.suffix.lower() == ".csv":
            item_count = max(0, text.count("\n") - 1)
        else:
            item_count = text.count("<item>")
    except Exception:
        item_count = 0

    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.execute(
            """INSERT INTO feed_snapshots
               (id, store_id, platform, country, file_path, item_count, created_at, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (sid, store_id, plat, cu, str(dest), item_count, now, job_id),
        )
        c.commit()

    prune_snapshots(store_id, plat, cu, keep=SNAPSHOT_KEEP)
    return sid


def prune_snapshots(store_id: str, platform: str, country: str, keep: int = SNAPSHOT_KEEP) -> int:
    init_snapshot_schema()
    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    with _conn() as c:
        rows = c.execute(
            """SELECT id, file_path FROM feed_snapshots
               WHERE store_id=? AND platform=? AND country=?
               ORDER BY created_at DESC""",
            (store_id, plat, cu),
        ).fetchall()
        drop = rows[keep:]
        for r in drop:
            try:
                Path(r["file_path"]).unlink(missing_ok=True)
            except Exception:
                pass
            c.execute("DELETE FROM feed_snapshots WHERE id=?", (r["id"],))
        c.commit()
    return len(drop)


def list_snapshots(store_id: str, platform: str, country: str) -> list[dict]:
    init_snapshot_schema()
    plat = (platform or "google").lower()
    cu = (country or "US").upper()
    with _conn() as c:
        rows = c.execute(
            """SELECT id, store_id, platform, country, file_path, item_count, created_at, job_id
               FROM feed_snapshots
               WHERE store_id=? AND platform=? AND country=?
               ORDER BY created_at DESC
               LIMIT ?""",
            (store_id, plat, cu, SNAPSHOT_KEEP),
        ).fetchall()
    out = []
    for r in rows:
        out.append({
            "id": r["id"],
            "platform": r["platform"],
            "country": r["country"],
            "item_count": r["item_count"] or 0,
            "created_at": r["created_at"],
            "job_id": r["job_id"],
            "download_path": f"/feeds/{store_id}/{plat}/_snapshots/{Path(r['file_path']).name}",
        })
    return out


def get_snapshot(store_id: str, snapshot_id: str) -> Optional[dict]:
    init_snapshot_schema()
    with _conn() as c:
        row = c.execute(
            """SELECT * FROM feed_snapshots WHERE id=? AND store_id=?""",
            (snapshot_id, store_id),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def restore_snapshot(store_id: str, snapshot_id: str) -> dict:
    """Copy snapshot file back to durable current path; update feed_files."""
    snap = get_snapshot(store_id, snapshot_id)
    if not snap:
        raise ValueError("snapshot not found")
    src = Path(snap["file_path"])
    if not src.exists():
        raise ValueError("snapshot file missing")

    plat = snap["platform"]
    cu = snap["country"]
    dest = durable_feed_path(FEEDS_DIR, store_id, plat, cu)
    # Read snapshot bytes first — snapshotting current may prune this snap file.
    payload = src.read_bytes()
    maybe_snapshot_current(store_id, plat, cu, dest)

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(payload)

    item_count = snap.get("item_count") or 0
    if dest.suffix.lower() != ".csv":
        try:
            item_count = dest.read_text(encoding="utf-8", errors="replace").count("<item>")
        except Exception:
            pass

    feed_url = durable_feed_url(PUBLIC_BASE_URL, store_id, plat, cu)
    try:
        if store_db.get_store(store_id):
            store_db.save_feed_file(
                store_id=store_id,
                country=cu,
                platform=plat,
                file_path=str(dest),
                feed_url=feed_url,
                item_count=item_count,
            )
    except Exception:
        # File restore already succeeded; feed_files row is best-effort.
        pass
    return {
        "ok": True,
        "platform": plat,
        "country": cu,
        "url": feed_url,
        "item_count": item_count,
        "restored_from": snapshot_id,
    }
