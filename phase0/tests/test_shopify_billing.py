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
    monkeypatch.setenv("ADFEED_QUOTA_FREE", "20")
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
    assert billing.quota_for_plan("free") == 20
    assert billing.quota_for_plan("starter") == 50
    assert billing.quota_for_plan("growth") == 200
    assert billing.normalize_plan_name("AdFeed Starter") == "starter"


def test_subscribe_returns_managed_pricing_url(app_client, monkeypatch):
    """Shopify App Pricing: do not call Billing API create; return hosted plan URL."""
    client, _, _ = app_client
    monkeypatch.setenv("SHOPIFY_APP_HANDLE", "adfeed-ai")
    token = _token()
    res = client.post(
        "/api/app/billing/subscribe",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan": "starter", "return_url": "https://deltfu.com/billing/return"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("managed_pricing") is True
    url = data.get("confirmation_url") or ""
    assert "admin.shopify.com/store/demo/charges/adfeed-ai/pricing_plans" in url
    assert data["plan"] == "starter"


def test_managed_pricing_plans_url_helper(app_client, monkeypatch):
    _, _, billing = app_client
    monkeypatch.setenv("SHOPIFY_APP_HANDLE", "adfeed-ai-3")
    url = billing.managed_pricing_plans_url("kakaku.myshopify.com")
    assert url == "https://admin.shopify.com/store/kakaku/charges/adfeed-ai-3/pricing_plans"


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


def test_billing_sync_applies_plan_handle(app_client):
    client, store_db, _ = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    res = client.post(
        "/api/app/billing/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"plan_handle": "growth"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["plan"] == "growth"
    assert data["quota_total"] == 200
    assert data["billing_status"] == "active"
    store = store_db.get_store_by_domain("demo.myshopify.com")
    assert store.plan == "growth"
    assert store.quota_total == 200


def test_managed_pricing_ignores_cancel_webhook_downgrade(app_client, monkeypatch):
    client, store_db, billing = app_client
    monkeypatch.setenv("ADFEED_MANAGED_PRICING", "true")
    import importlib
    importlib.reload(billing)
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    billing.apply_plan_handle(store.id, "starter")
    store = store_db.get_store(store.id)
    assert store.plan == "starter"
    billing.apply_subscription_webhook({
        "shop_domain": "demo.myshopify.com",
        "app_subscription": {
            "admin_graphql_api_id": "gid://shopify/AppSubscription/1",
            "name": "AdFeed Starter",
            "status": "CANCELLED",
        },
    })
    store = store_db.get_store(store.id)
    assert store.plan == "starter"
    assert store.quota_total == 50


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


def test_fetch_active_subscriptions_parses_shopify(app_client, monkeypatch):
    client, store_db, billing = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    store_db.update_store(store.id, access_token="shpat_test")
    store = store_db.get_store(store.id)

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "currentAppInstallation": {
                        "activeSubscriptions": [
                            {
                                "id": "gid://shopify/AppSubscription/1",
                                "name": "AdFeed Starter",
                                "status": "ACTIVE",
                                "createdAt": "2026-08-01T00:00:00Z",
                                "currentPeriodEnd": "2026-09-30T00:00:00Z",
                            }
                        ]
                    }
                }
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            assert "graphql" in url
            assert headers["X-Shopify-Access-Token"] == "shpat_test"
            return _Resp()

    monkeypatch.setattr(billing.httpx, "Client", _Client)
    subs = billing.fetch_active_app_subscriptions(store)
    assert len(subs) == 1
    assert subs[0]["name"] == "AdFeed Starter"
    assert subs[0]["created_at"] == "2026-08-01T00:00:00Z"
    assert subs[0]["current_period_end"] == "2026-09-30T00:00:00Z"


def test_cancel_app_subscriptions_best_effort(app_client, monkeypatch):
    client, store_db, billing = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    store_db.update_store(
        store.id,
        access_token="shpat_test",
        subscription_id="gid://shopify/AppSubscription/7",
    )
    store = store_db.get_store(store.id)

    calls = {"n": 0}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "data": {
                    "appSubscriptionCancel": {
                        "appSubscription": {
                            "id": "gid://shopify/AppSubscription/7",
                            "status": "CANCELLED",
                        },
                        "userErrors": [],
                    }
                }
            }

    class _Client:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def post(self, url, headers=None, json=None):
            calls["n"] += 1
            q = (json or {}).get("query", "")
            if "appSubscriptionCancel" in q:
                return _Resp()
            # activeSubscriptions probe during cancel — empty install
            class _Empty:
                def raise_for_status(self):
                    return None

                def json(self):
                    return {
                        "data": {
                            "currentAppInstallation": {"activeSubscriptions": []}
                        }
                    }

            return _Empty()

    monkeypatch.setattr(billing.httpx, "Client", _Client)
    result = billing.cancel_app_subscriptions(store)
    assert result["attempted"] >= 1
    assert "gid://shopify/AppSubscription/7" in result["cancelled_ids"]
    assert calls["n"] >= 1


def test_uninstall_cancels_before_clearing_token(app_client, monkeypatch):
    client, store_db, billing = app_client
    from adfeed.shopify_webhooks import handle_app_uninstalled

    token = _token("gone.myshopify.com")
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("gone.myshopify.com")
    store_db.update_store(
        store.id,
        access_token="shpat_live",
        plan="starter",
        billing_status="active",
        subscription_id="gid://shopify/AppSubscription/42",
        subscription_started_at="2026-09-01T00:00:00Z",
        subscription_period_end="2099-01-01T00:00:00Z",
    )
    seen = {"had_token": False}

    def _fake_cancel(st):
        seen["had_token"] = bool(st.access_token)
        return {
            "attempted": 1,
            "cancelled_ids": ["gid://shopify/AppSubscription/42"],
            "errors": [],
        }

    def _fake_snap(st):
        return {
            "id": "gid://shopify/AppSubscription/42",
            "name": "AdFeed Starter",
            "status": "ACTIVE",
            "created_at": "2026-09-01T00:00:00Z",
            "current_period_end": "2099-01-01T00:00:00Z",
        }

    import adfeed.shopify_billing as billing_mod

    monkeypatch.setattr(billing_mod, "cancel_app_subscriptions", _fake_cancel)
    monkeypatch.setattr(billing_mod, "snapshot_paid_period", _fake_snap)

    out = handle_app_uninstalled("gone.myshopify.com")
    assert out["ok"] is True
    assert seen["had_token"] is True
    updated = store_db.get_store(store.id)
    assert updated.access_token is None
    assert updated.status == "inactive"
    assert updated.billing_status == "cancelled"
    assert updated.plan == "free"
    assert updated.previous_plan == "starter"
    assert updated.quota_total == 50


def test_billing_status_includes_active_subscription(app_client, monkeypatch):
    client, store_db, billing = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    store_db.update_store(store.id, access_token="shpat_test", plan="free", billing_status="cancelled")

    def _fake_load(st):
        return True, [
            {
                "id": "gid://shopify/AppSubscription/9",
                "name": "AdFeed Growth",
                "status": "ACTIVE",
                "created_at": "2026-07-01T12:00:00Z",
                "current_period_end": "2026-10-01T12:00:00Z",
            }
        ]

    monkeypatch.setattr(billing, "load_active_app_subscriptions", _fake_load)
    import adfeed.shopify_billing as billing_mod

    monkeypatch.setattr(billing_mod, "load_active_app_subscriptions", _fake_load)

    res = client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["plan"] == "growth"
    assert data["billing_status"] == "active"
    assert data.get("billing_mode") == "active"
    sub = data.get("active_subscription") or {}
    assert sub["name"] == "AdFeed Growth"
    assert sub["status"] == "ACTIVE"
    assert sub["created_at"] == "2026-07-01T12:00:00Z"
    assert sub["current_period_end"] == "2026-10-01T12:00:00Z"
    assert sub.get("persists_after_reinstall") is False


def test_empty_active_keeps_paid_grace_period(app_client, monkeypatch):
    """Uninstall cancels → no active plan; banner still shows period details."""
    client, store_db, billing = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    store_db.update_store(
        store.id,
        access_token="shpat_test",
        plan="starter",
        billing_status="cancelled",
        previous_plan="starter",
        subscription_started_at="2026-09-01T00:00:00Z",
        subscription_period_end="2099-12-31T00:00:00Z",
    )

    def _fake_load(st):
        st._all_subscriptions_cache = []
        return True, []

    monkeypatch.setattr(billing, "load_active_app_subscriptions", _fake_load)
    import adfeed.shopify_billing as billing_mod

    monkeypatch.setattr(billing_mod, "load_active_app_subscriptions", _fake_load)
    monkeypatch.setattr(billing_mod, "_recover_grace_from_all_subscriptions", lambda st: None)

    res = client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["plan"] == "free"
    assert data["quota_total"] == 50
    assert data.get("billing_mode") == "paid_through"
    assert data.get("previous_plan") == "starter"
    sub = data.get("active_subscription") or {}
    assert sub.get("persists_after_reinstall") is True
    assert sub["current_period_end"].startswith("2099")
    assert sub["status"] == "CANCELLED"
    assert "Starter" in sub["name"]
    assert sub.get("created_at"), "banner start date required"
    assert sub.get("current_period_end"), "banner expiration required"


def test_grace_backfills_missing_start_date(app_client, monkeypatch):
    """Review banner needs start + end; backfill start from period_end if missing."""
    client, store_db, billing = app_client
    token = _token()
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("demo.myshopify.com")
    store_db.update_store(
        store.id,
        access_token="shpat_test",
        plan="free",
        billing_status="cancelled",
        previous_plan="growth",
        subscription_started_at=None,
        subscription_period_end="2099-12-31T00:00:00Z",
        quota_total=200,
    )

    def _fake_load(st):
        st._all_subscriptions_cache = []
        return True, []

    monkeypatch.setattr(billing, "load_active_app_subscriptions", _fake_load)
    import adfeed.shopify_billing as billing_mod

    monkeypatch.setattr(billing_mod, "load_active_app_subscriptions", _fake_load)
    monkeypatch.setattr(billing_mod, "_recover_grace_from_all_subscriptions", lambda st: None)

    res = client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data.get("billing_mode") == "paid_through"
    sub = data.get("active_subscription") or {}
    assert sub.get("persists_after_reinstall") is True
    assert sub["created_at"], "start date must be present"
    assert sub["current_period_end"].startswith("2099")
    refreshed = store_db.get_store(store.id)
    assert refreshed.subscription_started_at


def test_uninstall_snapshots_period_before_cancel(app_client, monkeypatch):
    client, store_db, billing = app_client
    from adfeed.shopify_webhooks import handle_app_uninstalled

    token = _token("snap.myshopify.com")
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("snap.myshopify.com")
    store_db.update_store(
        store.id,
        access_token="shpat_live",
        plan="growth",
        billing_status="active",
        subscription_id="gid://shopify/AppSubscription/55",
    )

    def _fake_snap(st):
        store_db.update_store(
            st.id,
            subscription_started_at="2026-09-01T00:00:00Z",
            subscription_period_end="2026-10-01T00:00:00Z",
        )
        return {
            "id": "gid://shopify/AppSubscription/55",
            "name": "AdFeed Growth",
            "status": "ACTIVE",
            "created_at": "2026-09-01T00:00:00Z",
            "current_period_end": "2026-10-01T00:00:00Z",
        }

    def _fake_cancel(st):
        return {"attempted": 1, "cancelled_ids": ["gid://shopify/AppSubscription/55"], "errors": []}

    import adfeed.shopify_billing as billing_mod

    monkeypatch.setattr(billing_mod, "snapshot_paid_period", _fake_snap)
    monkeypatch.setattr(billing_mod, "cancel_app_subscriptions", _fake_cancel)

    out = handle_app_uninstalled("snap.myshopify.com")
    assert out["ok"] is True
    assert out.get("period_snapshot")
    updated = store_db.get_store(store.id)
    assert updated.subscription_period_end == "2026-10-01T00:00:00Z"
    assert updated.plan == "free"
    assert updated.previous_plan == "growth"
    assert updated.access_token is None
