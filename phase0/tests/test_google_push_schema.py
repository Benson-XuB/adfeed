"""Google API push schema: data_source_name + push runs/items."""
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def store_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    from adfeed import store_db

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"p-{uuid.uuid4().hex[:8]}@ex.com", name="P")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="Push Store",
    )
    return store_db, store


def test_google_push_tables_and_datasource(store_env):
    store_db, store = store_env
    store_db.upsert_google_merchant_account(store.id, "12345", "MC", select=True)
    ds = "accounts/12345/dataSources/api-primary"
    row = store_db.set_merchant_data_source(store.id, "12345", ds)
    assert row["data_source_name"] == ds
    assert row["data_source_name"].startswith("accounts/")

    run = store_db.create_push_run(store.id, "12345")
    store_db.add_push_item(
        run["id"],
        offer_id="SKU-1",
        status="ok",
    )
    finished = store_db.finish_push_run(run["id"], ok_count=1, fail_count=0, status="done")
    assert finished["status"] == "done"
    assert finished["ok_count"] == 1
    assert finished["fail_count"] == 0
    assert finished["finished_at"]

    items = store_db.list_push_items(run["id"])
    assert items[0]["offer_id"] == "SKU-1"

    with pytest.raises(ValueError, match="offer_id"):
        store_db.add_push_item(run["id"], offer_id="  ")


def test_purge_and_oauth_delete_clear_push_tables(store_env):
    store_db, store = store_env
    store_db.upsert_google_oauth_token(store.id, "enc-token", "scope")
    store_db.upsert_google_merchant_account(store.id, "99", "MC", select=True)
    run = store_db.create_push_run(store.id, "99")
    store_db.add_push_item(run["id"], offer_id="SKU-1", status="ok")
    assert store_db.list_push_items(run["id"])

    store_db.delete_google_oauth_token(store.id)
    assert store_db.list_push_items(run["id"]) == []
    with store_db._conn() as c:
        n = c.execute(
            "SELECT COUNT(*) AS n FROM google_push_runs WHERE store_id = ?",
            (store.id,),
        ).fetchone()["n"]
    assert n == 0

    store_db.upsert_google_oauth_token(store.id, "enc-token", "scope")
    store_db.upsert_google_merchant_account(store.id, "99", "MC", select=True)
    run2 = store_db.create_push_run(store.id, "99")
    store_db.add_push_item(run2["id"], offer_id="SKU-2", status="fail")
    assert store_db.purge_store_data(store.id) is True
    with store_db._conn() as c:
        n_runs = c.execute(
            "SELECT COUNT(*) AS n FROM google_push_runs WHERE store_id = ?",
            (store.id,),
        ).fetchone()["n"]
        n_items = c.execute(
            "SELECT COUNT(*) AS n FROM google_push_items WHERE run_id = ?",
            (run2["id"],),
        ).fetchone()["n"]
    assert n_runs == 0
    assert n_items == 0
