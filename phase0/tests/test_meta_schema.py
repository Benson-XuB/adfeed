"""Meta oauth + catalog schema."""
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
    user = create_user(email=f"m-{uuid.uuid4().hex[:8]}@ex.com", name="M")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="M",
    )
    return store_db, store


def test_meta_oauth_and_catalog_tables(store_env):
    store_db, store = store_env
    store_db.upsert_meta_oauth_token(store.id, "enc-token", "catalog_management")
    tok = store_db.get_meta_oauth_token(store.id)
    assert tok["access_token_enc"] == "enc-token"
    row = store_db.upsert_meta_catalog(
        store.id, "cat-1", "Main Catalog", select=True
    )
    assert row["catalog_id"] == "cat-1"
    assert store_db.get_selected_meta_catalog_id(store.id) == "cat-1"


def test_purge_clears_meta(store_env):
    store_db, store = store_env
    store_db.upsert_meta_oauth_token(store.id, "enc", "catalog_management")
    store_db.upsert_meta_catalog(store.id, "c1", select=True)
    store_db.purge_store_data(store.id)
    assert store_db.get_meta_oauth_token(store.id) is None
    assert store_db.list_meta_catalogs(store.id) == []
