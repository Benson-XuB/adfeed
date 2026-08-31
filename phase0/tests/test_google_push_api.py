"""Google push API: feature flag, POST push, GET run."""
import sys
import time
import uuid
from pathlib import Path

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOP = "push-api.myshopify.com"
MERCHANT_ID = "12345"
DATA_SOURCE = "accounts/12345/dataSources/api-primary"


@pytest.fixture()
def client_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://example.test")
    monkeypatch.delenv("GOOGLE_PUSH_ENABLED", raising=False)
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
    user = create_user(email=f"push-{uuid.uuid4().hex[:8]}@ex.com", name="Push")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=SHOP,
        shop_name="Push API",
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


def _row(sku: str):
    return {
        "SKU": sku,
        "优化后标题": f"Title {sku}",
        "描述": "Desc",
        "颜色": "White",
        "价格": 10.0,
        "图片链接": "https://example.com/a.jpg",
        "链接": "https://example.com/p",
        "品牌": "Northline",
        "尺码": "M",
        "库存": 5,
        "_feed_currency": "USD",
        "identifier_exists": "no",
    }


def _setup_merchant(store_db, store, *, with_data_source: bool = True):
    store_db.upsert_google_merchant_account(store.id, MERCHANT_ID, "MC", select=True)
    if with_data_source:
        store_db.set_merchant_data_source(store.id, MERCHANT_ID, DATA_SOURCE)


def test_google_push_enabled_helper(monkeypatch):
    from adfeed.platforms.google.router import google_push_enabled

    monkeypatch.delenv("GOOGLE_PUSH_ENABLED", raising=False)
    assert google_push_enabled() is False
    for val in ("0", "false", "no", ""):
        monkeypatch.setenv("GOOGLE_PUSH_ENABLED", val)
        assert google_push_enabled() is False, val
    for val in ("1", "true", "yes", "TRUE", "Yes"):
        monkeypatch.setenv("GOOGLE_PUSH_ENABLED", val)
        assert google_push_enabled() is True, val


def test_status_includes_push_enabled(client_env, monkeypatch):
    client, _store_db, _store = client_env
    monkeypatch.delenv("GOOGLE_PUSH_ENABLED", raising=False)
    res = client.get("/api/app/google/status", headers=_auth_headers())
    assert res.status_code == 200, res.text
    body = res.json()
    assert "push_enabled" in body
    assert body["push_enabled"] is False

    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    res2 = client.get("/api/app/google/status", headers=_auth_headers())
    assert res2.status_code == 200, res2.text
    assert res2.json()["push_enabled"] is True


def test_push_disabled_returns_503(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.delenv("GOOGLE_PUSH_ENABLED", raising=False)
    _setup_merchant(store_db, store)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"rows": [_row("SKU-1")], "use_fake": True},
    )
    assert res.status_code == 503


def test_push_with_flag_and_fake_returns_run(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    _setup_merchant(store_db, store)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={
            "rows": [_row("OK-1"), _row("OK-2")],
            "use_fake": True,
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"]
    assert body["ok_count"] == 2
    assert body["fail_count"] == 0
    assert body["status"] == "done"
    assert store_db.list_push_items(body["id"])


def test_push_with_mock_result_uses_fake_path(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "true")
    _setup_merchant(store_db, store)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={
            "rows": [_row("MOCK-1")],
            "mock_result": {"note": "ci"},
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok_count"] == 1
    assert body["id"]


def test_push_missing_rows_returns_400(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    _setup_merchant(store_db, store)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"use_fake": True},
    )
    assert res.status_code == 400


def test_push_requires_data_source(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    _setup_merchant(store_db, store, with_data_source=False)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"rows": [_row("SKU-1")], "use_fake": True},
    )
    assert res.status_code == 400


def test_get_push_run_summary_and_items(client_env, monkeypatch):
    client, store_db, store = client_env
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    _setup_merchant(store_db, store)
    push = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"rows": [_row("RUN-1")], "use_fake": True},
    )
    assert push.status_code == 200, push.text
    run_id = push.json()["id"]

    res = client.get(
        f"/api/app/google/push/runs/{run_id}",
        headers=_auth_headers(),
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == run_id
    assert body["ok_count"] == 1
    assert body["status"] == "done"
    assert isinstance(body["items"], list)
    assert body["items"][0]["offer_id"] == "RUN-1"
    assert body["items"][0]["status"] == "ok"
