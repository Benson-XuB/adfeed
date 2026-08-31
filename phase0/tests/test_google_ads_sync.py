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
        def list_product_metrics(self, ads_customer_id: str, window_days: int = 7):
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
    assert r["window_days"] == 7
    rows = store_db.list_ads_metrics_daily(
        store.id, "111", product_level_only=True, window_days=7
    )
    assert rows[0]["offer_id"] == "SKU-1"
    assert rows[0]["window_days"] == 7


def test_ads_sync_degraded_without_offer(store_env):
    store_db, store, sync_ads_metrics = store_env

    class Fake:
        def list_product_metrics(self, ads_customer_id: str, window_days: int = 7):
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


def test_ads_sync_7_and_30_windows_do_not_overwrite(store_env):
    store_db, store, sync_ads_metrics = store_env

    class Fake:
        def list_product_metrics(self, ads_customer_id: str, window_days: int = 7):
            if window_days == 30:
                return [
                    {
                        "date": "2026-08-01",
                        "offer_id": "SKU-30",
                        "impressions": 30,
                        "clicks": 3,
                        "cost_micros": 3000,
                        "conversions": 1,
                    }
                ]
            return [
                {
                    "date": "2026-08-29",
                    "offer_id": "SKU-7",
                    "impressions": 7,
                    "clicks": 1,
                    "cost_micros": 700,
                    "conversions": 0,
                }
            ]

    r7 = sync_ads_metrics(store.id, "333", Fake(), window_days=7)
    r30 = sync_ads_metrics(store.id, "333", Fake(), window_days=30)
    assert r7["written"] == 1
    assert r30["written"] == 1

    rows7 = store_db.list_ads_metrics_daily(store.id, "333", window_days=7)
    rows30 = store_db.list_ads_metrics_daily(store.id, "333", window_days=30)
    assert len(rows7) == 1 and rows7[0]["offer_id"] == "SKU-7"
    assert len(rows30) == 1 and rows30[0]["offer_id"] == "SKU-30"

    # Re-sync 7 must not wipe 30
    sync_ads_metrics(store.id, "333", Fake(), window_days=7)
    assert len(store_db.list_ads_metrics_daily(store.id, "333", window_days=30)) == 1
    assert len(store_db.list_ads_metrics_daily(store.id, "333", window_days=7)) == 1
