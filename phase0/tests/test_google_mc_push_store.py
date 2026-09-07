"""store_google_mc connection helpers."""
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def fresh_db(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    from adfeed.db import init_db, create_user

    init_db()
    from adfeed import store_db

    store_db.init_store_schema()
    user = create_user(email=f"gmc-{uuid.uuid4().hex[:8]}@example.com", name="GMC")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="Demo",
        quota_total=50,
    )
    return store_db, store


def test_upsert_and_get_google_connection(fresh_db):
    store_db, store = fresh_db
    assert store_db.get_google_connection(store.id) is None

    row = store_db.upsert_google_connection(
        store.id,
        refresh_token="rt-1",
        access_token="at-1",
        token_expiry="2099-01-01T00:00:00Z",
        merchant_id="123456",
        data_source_id="104628",
        data_source_name="AdFeed",
    )
    assert row["merchant_id"] == "123456"
    assert row["data_source_id"] == "104628"
    assert row["refresh_token"] == "rt-1"

    again = store_db.get_google_connection(store.id)
    assert again["access_token"] == "at-1"

    store_db.upsert_google_connection(store.id, merchant_id="999")
    assert store_db.get_google_connection(store.id)["merchant_id"] == "999"
    # tokens preserved on partial upsert
    assert store_db.get_google_connection(store.id)["refresh_token"] == "rt-1"


def test_save_and_latest_push_run(fresh_db):
    store_db, store = fresh_db
    rid = store_db.save_google_push_run(
        store.id,
        merchant_id="123",
        data_source_id="9",
        status="completed",
        success_count=2,
        failure_count=1,
        failures=[{"offer_id": "X", "error": "bad"}],
    )
    assert rid
    latest = store_db.latest_google_push_run(store.id)
    assert latest["success_count"] == 2
    assert latest["failure_count"] == 1
    assert "X" in latest["failures_json"]
