"""store_db schema tests — billing, product_assets, usage_ledger, store_jobs"""
import os
import sys
import uuid
import tempfile
from pathlib import Path

import pytest

# Ensure phase0 is on path and use isolated DB before importing adfeed.*
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def fresh_db(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    # Drop cached modules so DB_PATH is re-evaluated
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    from adfeed.db import init_db, create_user
    init_db()  # users table must exist before store_db schema (FK)
    from adfeed import store_db
    store_db.init_store_schema()
    user = create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", name="Tester")
    return store_db, user


def test_store_has_billing_and_quota_fields(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="Demo",
        quota_total=120,
    )
    assert store.quota_total == 120
    assert store.quota_used == 0
    assert store.quota_remaining == 120
    assert store.plan == "free"
    assert store.billing_status == "none"
    assert store.subscription_id is None


def test_update_store_billing_fields(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
    )
    store_db.update_store(
        store.id,
        plan="starter",
        quota_total=400,
        subscription_id="gid://shopify/AppSubscription/1",
        billing_status="active",
    )
    refreshed = store_db.get_store(store.id)
    assert refreshed.plan == "starter"
    assert refreshed.quota_total == 400
    assert refreshed.billing_status == "active"
    assert refreshed.subscription_id.endswith("/1")


def test_product_assets_unique_key(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
    )
    # Minimal product row
    from adfeed.db import _conn
    pid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            """INSERT INTO products (id, store_id, title, status)
               VALUES (?, ?, ?, 'active')""",
            (pid, store.id, "Test Dress"),
        )
        c.commit()

    a1 = store_db.upsert_product_asset(
        store.id, pid, "google", "US", title="Title A", description="Desc A",
    )
    a2 = store_db.upsert_product_asset(
        store.id, pid, "google", "US", title="Title B", description="Desc B",
    )
    assert a1.id == a2.id
    assert a2.title == "Title B"

    a3 = store_db.upsert_product_asset(
        store.id, pid, "meta", "US", title="Meta Title",
    )
    assert a3.id != a1.id
    assert store_db.get_product_asset_by_key(pid, "google", "US").title == "Title B"


def test_usage_ledger_increments_quota(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        quota_total=10,
    )
    store_db.record_usage(store.id, "google", "US", sku="SKU1")
    store_db.record_usage(store.id, "meta", "DE", sku="SKU1")
    refreshed = store_db.get_store(store.id)
    assert refreshed.quota_used == 2
    assert refreshed.quota_remaining == 8


def test_store_job_crud(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
    )
    job = store_db.create_store_job(
        store.id,
        platforms=["google", "meta"],
        languages=["US"],
        product_ids=["p1", "p2"],
        total_units=4,
    )
    assert job.status == "pending"
    assert job.total_units == 4
    store_db.update_store_job(job.id, status="completed", ok_units=4, done_units=4)
    job2 = store_db.get_store_job(job.id)
    assert job2.status == "completed"
    assert job2.ok_units == 4
