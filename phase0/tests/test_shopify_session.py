"""Shopify session auth tests"""
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

    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    # Reload config with new env
    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"

    from adfeed.db import init_db
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()

    from adfeed.api import app
    return TestClient(app), cfg


def _make_token(shop: str = "demo.myshopify.com", secret: str = "test-client-secret",
                aud: str = "test-client-id", exp_delta: int = 60) -> str:
    now = int(time.time())
    payload = {
        "iss": f"https://{shop}/admin",
        "dest": f"https://{shop}",
        "aud": aud,
        "sub": "1",
        "exp": now + exp_delta,
        "nbf": now - 5,
        "iat": now,
        "jti": str(uuid.uuid4()),
        "sid": str(uuid.uuid4()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_app_route_rejects_missing_token(app_client):
    client, _ = app_client
    res = client.get("/api/app/billing/status")
    assert res.status_code == 401


def test_app_route_rejects_bad_token(app_client):
    client, _ = app_client
    res = client.get(
        "/api/app/billing/status",
        headers={"Authorization": "Bearer not-a-jwt"},
    )
    assert res.status_code == 401


def test_app_route_accepts_valid_session(app_client):
    client, _ = app_client
    token = _make_token()
    res = client.get(
        "/api/app/billing/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["shop_domain"] == "demo.myshopify.com"
    assert "quota_remaining" in data


def test_legacy_open_feed_disabled(app_client):
    client, _ = app_client
    res = client.post("/api/shopify/feed", json={
        "shop_domain": "demo.myshopify.com",
        "product_ids": ["1"],
        "countries": ["US"],
    })
    assert res.status_code in (401, 403, 410)


def test_app_products_requires_session(app_client):
    client, _ = app_client
    assert client.get("/api/app/products").status_code == 401
    token = _make_token()
    res = client.get(
        "/api/app/products",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["shop_domain"] == "demo.myshopify.com"
    assert "products" in data
