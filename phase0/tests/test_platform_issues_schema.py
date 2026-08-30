"""Schema for Meta/TikTok product issues tables."""
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
    user = create_user(email=f"i-{uuid.uuid4().hex[:8]}@ex.com", name="I")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="I",
    )
    return store_db, store


def test_meta_and_tiktok_issues_tables(store_env):
    store_db, store = store_env
    n = store_db.replace_meta_product_issues(
        store.id,
        "cat-1",
        [
            {
                "offer_id": "SKU-1",
                "product_id_internal": "SKU-1",
                "status": "disapproved",
                "reason_code": "image_missing",
                "reason_text": "need image",
            }
        ],
    )
    assert n == 1
    rows = store_db.list_meta_product_issues(store.id, "cat-1")
    assert rows[0]["offer_id"] == "SKU-1"

    n2 = store_db.replace_tiktok_product_issues(
        store.id,
        "shop-1",
        [
            {
                "offer_id": "SKU-2",
                "status": "rejected",
                "reason_code": "title_issue",
                "reason_text": "bad title",
            }
        ],
    )
    assert n2 == 1
    assert store_db.list_tiktok_product_issues(store.id, "shop-1")[0]["offer_id"] == "SKU-2"


def test_purge_clears_platform_issues(store_env):
    store_db, store = store_env
    store_db.replace_meta_product_issues(
        store.id, "c1", [{"offer_id": "A", "status": "x"}]
    )
    store_db.replace_tiktok_product_issues(
        store.id, "s1", [{"offer_id": "B", "status": "y"}]
    )
    store_db.purge_store_data(store.id)
    # store gone — helpers should not find rows for deleted store
    assert store_db.list_meta_product_issues(store.id, "c1") == []
    assert store_db.list_tiktok_product_issues(store.id, "s1") == []
