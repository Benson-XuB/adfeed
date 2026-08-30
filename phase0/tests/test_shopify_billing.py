"""Shopify billing + plan → quota sync tests"""
import sys
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def app_client(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_QUOTA_FREE", "3")
    monkeypatch.setenv("ADFEED_QUOTA_STARTER", "50")
    monkeypatch.setenv("ADFEED_QUOTA_GROWTH", "200")

    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"

    from adfeed.db import init_db
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()

    # Reload billing module quotas after env set
    import importlib
    import adfeed.shopify_billing as billing
    importlib.reload(billing)

    from adfeed.api import app
    return TestClient(app), store_db, billing


def _token(shop="demo.myshopify.com"):
    now = int(time.time())
    return jwt.encode(
        {
            "iss": f"https://{shop}/admin",
            "dest": f"https://{shop}",
            "aud": "test-client-id",
            "sub": "1",
            "exp": now + 60,
            "nbf": now - 5,
            "iat": now,
            "jti": str(uuid.uuid4()),
        },
        "test-client-secret",
        algorithm="HS256",
    )


def test_plan_quota_mapping(app_client):
    _, _, billing = app_client
    assert billing.quota_for_plan("free") == 3
    assert billing.quota_for_plan("starter") == 50
    assert billing.quota_for_plan("growth") == 200
    assert billing.normalize_plan_name("AdFeed Starter") == "starter"


def test_subscribe_returns_confirmation_url(app_client):
    client, store_db, _ = app_client
    token = _token()
    res = client.post(
        "/api/app/billing/subscribe",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "starter", "return_url": "https://deltfu.com/billing/return"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "confirmation_url" in data
    assert data["plan"] == "starter"
    assert data["quota_total"] == 50


def test_subscription_webhook_updates_quota(app_client):
    client, store_db, billing = app_client
    # Ensure store exists
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    assert store

    store_db.update_store(store.id, subscription_id="gid://shopify/AppSubscription/99")

    updated = billing.apply_subscription_webhook({
        "shop_domain": "demo.myshopify.com",
        "app_subscription": {
            "admin_graphql_api_id": "gid://shopify/AppSubscription/99",
            "name": "AdFeed Growth",
            "status": "ACTIVE",
        },
    })
    assert updated is not None
    assert updated.plan == "growth"
    assert updated.quota_total == 200
    assert updated.billing_status == "active"


def test_subscribe_requires_session(app_client):
    client, _, _ = app_client
    res = client.post("/api/app/billing/subscribe", json={"plan": "starter"})
    assert res.status_code == 401


def test_billing_test_charges_off_by_default(app_client, monkeypatch):
    _, _, billing = app_client
    monkeypatch.delenv("ADFEED_BILLING_TEST", raising=False)
    assert billing.billing_test_charges() is False


def test_billing_return_redirects_to_admin(app_client):
    client, _, _ = app_client
    res = client.get(
        "/api/app/billing/return",
        params={"shop": "demo.myshopify.com"},
        follow_redirects=False,
    )
    assert res.status_code in (302, 303, 307, 308)
    loc = res.headers.get("location") or ""
    assert "admin.shopify.com" in loc
    assert "demo" in loc
