import sys
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
    user = create_user(email=f"is-{__import__('uuid').uuid4().hex[:8]}@ex.com", name="IS")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{__import__('uuid').uuid4().hex[:8]}.myshopify.com",
        shop_name="IS",
    )
    return store_db, store


def test_issues_from_meta_products():
    from adfeed.platforms.meta.catalog_client import issues_from_meta_products

    rows = issues_from_meta_products(
        {
            "data": [
                {
                    "id": "p1",
                    "retailer_id": "SKU-1",
                    "review_status": "REJECTED",
                    "review_rejection_reasons": [
                        {"reason": "MISSING_IMAGE", "description": "Add image"}
                    ],
                },
                {
                    "id": "p2",
                    "retailer_id": "SKU-OK",
                    "review_status": "APPROVED",
                },
            ]
        }
    )
    assert len(rows) == 1
    assert rows[0]["offer_id"] == "SKU-1"
    assert rows[0]["reason_code"] == "MISSING_IMAGE"


def test_issues_from_tiktok_diagnoses():
    from adfeed.platforms.tiktok.shop_client import issues_from_tiktok_diagnoses

    rows = issues_from_tiktok_diagnoses(
        {
            "data": {
                "products": [
                    {
                        "seller_sku": "SKU-T",
                        "issues": [{"code": "title_too_long", "message": "Shorten"}],
                    }
                ]
            }
        }
    )
    assert rows[0]["offer_id"] == "SKU-T"
    assert "title" in rows[0]["reason_code"]


def test_sync_meta_and_tiktok_matched(store_env):
    store_db, store = store_env
    from adfeed.platforms.meta.issues_sync import sync_meta_issues
    from adfeed.platforms.tiktok.issues_sync import sync_tiktok_issues

    class FakeMeta:
        def list_product_issues(self, catalog_id: str):
            return [
                {
                    "offer_id": "SKU-1",
                    "status": "disapproved",
                    "reason_code": "image_missing",
                    "reason_text": "img",
                },
                {
                    "offer_id": "NOPE",
                    "status": "disapproved",
                    "reason_code": "other",
                    "reason_text": "x",
                },
            ]

    class FakeTt:
        def list_product_issues(self, shop_id: str):
            return [
                {
                    "offer_id": "SKU-1",
                    "status": "rejected",
                    "reason_code": "color_missing",
                    "reason_text": "color",
                }
            ]

    r = sync_meta_issues(store.id, "cat-1", FakeMeta(), sku_set={"SKU-1"})
    assert r["matched"] == 1 and r["unmatched"] == 1
    r2 = sync_tiktok_issues(store.id, "shop-1", FakeTt(), sku_set={"SKU-1"})
    assert r2["matched"] == 1
    assert store_db.list_tiktok_product_issues(store.id, "shop-1")[0][
        "product_id_internal"
    ] == "SKU-1"
