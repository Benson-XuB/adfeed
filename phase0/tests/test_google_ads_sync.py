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
    from adfeed.google_ads_sync import sync_ads_metrics

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"a-{uuid.uuid4().hex[:8]}@ex.com", name="A")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="A",
    )
    return store_db, store, sync_ads_metrics


def test_ads_sync_product_level(store_env):
    store_db, store, sync_ads_metrics = store_env

    class Fake:
        def list_product_metrics(self, ads_customer_id: str):
            return [
                {
                    "date": "2026-08-29",
                    "offer_id": "SKU-1",
                    "impressions": 10,
                    "clicks": 2,
                    "cost_micros": 1000,
                    "conversions": 0,
                }
            ]

    r = sync_ads_metrics(store.id, "111", Fake())
    assert r["product_level"] == 1
    assert r["degraded"] is False
    rows = store_db.list_ads_metrics_daily(store.id, "111", product_level_only=True)
    assert rows[0]["offer_id"] == "SKU-1"


def test_ads_sync_degraded_without_offer(store_env):
    store_db, store, sync_ads_metrics = store_env

    class Fake:
        def list_product_metrics(self, ads_customer_id: str):
            return [
                {
                    "date": "2026-08-29",
                    "campaign_id": "c1",
                    "impressions": 10,
                    "clicks": 1,
                    "cost_micros": 500,
                }
            ]

    r = sync_ads_metrics(store.id, "222", Fake())
    assert r["degraded"] is True
