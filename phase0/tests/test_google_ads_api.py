"""Google Ads metrics API: summary, window filter, settings persistence."""
import sys
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOP = "ads-api.myshopify.com"


@pytest.fixture()
def client_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://example.test")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg

    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    cfg.PUBLIC_BASE_URL = "https://example.test"
    cfg.WEB_SAAS_ENABLED = False

    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.api import app

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"ads-{uuid.uuid4().hex[:8]}@ex.com", name="Ads")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=SHOP,
        shop_name="Ads API",
    )
    return TestClient(app), store_db, store


def _token(shop=SHOP):
    now = int(time.time())
    return jwt.encode(
        {
            "iss": f"https://{shop}/admin",
            "dest": f"https://{shop}",
            "aud": "test-client-id",
            "sub": "1",
            "exp": now + 120,
            "nbf": now - 5,
            "iat": now,
            "jti": str(uuid.uuid4()),
        },
        "test-client-secret",
        algorithm="HS256",
    )


def _auth_headers():
    return {"Authorization": f"Bearer {_token()}"}


def test_ads_metrics_summary_and_settings(client_env):
    client, store_db, store = client_env
    cid = "9998887776"

    sync = client.post(
        "/api/app/google/ads/sync",
        headers=_auth_headers(),
        json={
            "ads_customer_id": cid,
            "window_days": 7,
            "mock_rows": [
                {
                    "date": "2026-08-29",
                    "offer_id": "SKU-A",
                    "impressions": 10,
                    "clicks": 2,
                    "cost_micros": 1000,
                    "conversions": 0.5,
                },
                {
                    "date": "2026-08-28",
                    "offer_id": "SKU-B",
                    "impressions": 5,
                    "clicks": 1,
                    "cost_micros": 500,
                    "conversions": 0.25,
                },
            ],
        },
    )
    assert sync.status_code == 200, sync.text
    body = sync.json()
    assert body["written"] == 2
    assert body["window_days"] == 7

    metrics = client.get(
        f"/api/app/google/ads/metrics?ads_customer_id={cid}&window_days=7",
        headers=_auth_headers(),
    )
    assert metrics.status_code == 200, metrics.text
    m = metrics.json()
    assert m["window_days"] == 7
    assert m["product_level"] == 2
    assert m["degraded"] is False
    assert m["summary"]["impressions"] == 15
    assert m["summary"]["clicks"] == 3
    assert m["summary"]["cost_micros"] == 1500
    assert m["summary"]["conversions"] == pytest.approx(0.75)

    settings = client.get("/api/app/google/ads/settings", headers=_auth_headers())
    assert settings.status_code == 200, settings.text
    s = settings.json()
    assert s["ads_customer_id"] == cid
    assert s["window_days"] == 7

    status = client.get("/api/app/google/status", headers=_auth_headers())
    assert status.status_code == 200, status.text
    st = status.json()
    assert st["ads_customer_id"] == cid
    assert st["ads_window_days"] == 7


def test_ads_metrics_windows_isolated_via_api(client_env):
    client, _store_db, _store = client_env
    cid = "1112223334"

    for wd, offer in ((7, "SKU-7"), (30, "SKU-30")):
        res = client.post(
            "/api/app/google/ads/sync",
            headers=_auth_headers(),
            json={
                "ads_customer_id": cid,
                "window_days": wd,
                "mock_rows": [
                    {
                        "date": "2026-08-20",
                        "offer_id": offer,
                        "impressions": wd,
                        "clicks": 1,
                        "cost_micros": wd * 100,
                        "conversions": 0,
                    }
                ],
            },
        )
        assert res.status_code == 200, res.text

    m7 = client.get(
        f"/api/app/google/ads/metrics?ads_customer_id={cid}&window_days=7",
        headers=_auth_headers(),
    ).json()
    m30 = client.get(
        f"/api/app/google/ads/metrics?ads_customer_id={cid}&window_days=30",
        headers=_auth_headers(),
    ).json()
    assert len(m7["rows"]) == 1 and m7["rows"][0]["offer_id"] == "SKU-7"
    assert m7["summary"]["impressions"] == 7
    assert len(m30["rows"]) == 1 and m30["rows"][0]["offer_id"] == "SKU-30"
    assert m30["summary"]["impressions"] == 30
