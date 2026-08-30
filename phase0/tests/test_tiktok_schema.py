"""TikTok oauth + shops schema."""
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
    user = create_user(email=f"t-{uuid.uuid4().hex[:8]}@ex.com", name="T")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="T",
    )
    return store_db, store


def test_tiktok_oauth_and_shops_tables(store_env):
    store_db, store = store_env
    store_db.upsert_tiktok_oauth_token(
        store.id, "enc-rt", "enc-at", "seller.product.write"
    )
    tok = store_db.get_tiktok_oauth_token(store.id)
    assert tok["refresh_token_enc"] == "enc-rt"
    row = store_db.upsert_tiktok_shop(
        store.id, "shop-1", "My Shop", select=True, feed_url="https://x/f.csv"
    )
    assert row["shop_id"] == "shop-1"
    assert store_db.get_selected_tiktok_shop_id(store.id) == "shop-1"
    assert row["feed_url"].endswith(".csv")


def test_purge_clears_tiktok(store_env):
    store_db, store = store_env
    store_db.upsert_tiktok_oauth_token(store.id, "r", "a", "")
    store_db.upsert_tiktok_shop(store.id, "s1", select=True)
    store_db.purge_store_data(store.id)
    assert store_db.get_tiktok_oauth_token(store.id) is None
    assert store_db.list_tiktok_shops(store.id) == []
