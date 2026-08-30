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
    user = create_user(email=f"s-{uuid.uuid4().hex[:8]}@ex.com", name="S")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="S",
    )
    return store_db, store


def test_sync_writes_matched_and_unmatched(store_env):
    store_db, store = store_env
    from adfeed.google_merchant_sync import sync_merchant_issues

    class FakeMerchantClient:
        def list_product_issues(self, merchant_id: str):
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

    result = sync_merchant_issues(
        store.id, "m1", FakeMerchantClient(), sku_set={"SKU-1"}
    )
    assert result["matched"] == 1
    assert result["unmatched"] == 1
    rows = store_db.list_gmc_product_issues(store.id, "m1")
    by_oid = {r["offer_id"]: r for r in rows}
    assert by_oid["SKU-1"]["product_id_internal"] == "SKU-1"
    assert by_oid["NOPE"]["product_id_internal"] is None
