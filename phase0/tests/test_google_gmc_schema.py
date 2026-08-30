"""Google GMC schema + sync helpers."""
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
    user = create_user(email=f"g-{uuid.uuid4().hex[:8]}@ex.com", name="G")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="G Store",
    )
    return store_db, store


def test_google_merchant_accounts_and_issues_tables_exist(store_env):
    store_db, store = store_env
    store_db.upsert_google_oauth_token(store.id, "enc-token", "https://www.googleapis.com/auth/content")
    store_db.upsert_google_merchant_account(store.id, "12345", "MC", select=True)
    n = store_db.replace_gmc_product_issues(
        store.id,
        "12345",
        [
            {
                "offer_id": "SKU-1",
                "product_id_internal": "SKU-1",
                "status": "disapproved",
                "reason_code": "image_missing",
                "reason_text": "missing image",
            }
        ],
    )
    assert n == 1
    rows = store_db.list_gmc_product_issues(store.id, "12345")
    assert rows[0]["offer_id"] == "SKU-1"
    assert rows[0]["status"] == "disapproved"


def test_purge_clears_google_tables(store_env):
    store_db, store = store_env
    store_db.upsert_google_oauth_token(store.id, "enc", "scope")
    store_db.upsert_google_merchant_account(store.id, "9", select=True)
    store_db.replace_gmc_product_issues(
        store.id, "9", [{"offer_id": "A", "status": "disapproved"}]
    )
    assert store_db.purge_store_data(store.id) is True
    assert store_db.get_google_oauth_token(store.id) is None
    assert store_db.list_google_merchant_accounts(store.id) == []
