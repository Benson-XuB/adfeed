"""Quota estimate + enforce tests"""
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
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    from adfeed.db import init_db, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    from adfeed.quota import estimate_cost, assert_quota_available, debit_quota
    user = create_user(email=f"q-{uuid.uuid4().hex[:8]}@ex.com", name="Q")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain="quota.myshopify.com",
        quota_total=10,
    )
    return store_db, store, estimate_cost, assert_quota_available, debit_quota


def test_estimate_cost_sku_x_platform_x_language(env):
    _, _, estimate_cost, _, _ = env
    assert estimate_cost(3, ["google", "meta"], ["US", "DE"]) == 12
    assert estimate_cost(1, ["google"], ["US"]) == 1
    assert estimate_cost(0, ["google"], ["US"]) == 0


def test_assert_blocks_when_insufficient(env):
    from fastapi import HTTPException
    _, store, estimate_cost, assert_quota_available, _ = env
    cost = estimate_cost(5, ["google", "meta"], ["US", "DE"])  # 20
    with pytest.raises(HTTPException) as ei:
        assert_quota_available(store, cost)
    assert ei.value.status_code == 402


def test_debit_increments_used(env):
    store_db, store, _, _, debit_quota = env
    debit_quota(store.id, "google", "US", sku="SKU1")
    debit_quota(store.id, "meta", "DE", sku="SKU1")
    refreshed = store_db.get_store(store.id)
    assert refreshed.quota_used == 2
    assert refreshed.quota_remaining == 8


def test_generate_rejects_over_quota(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
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
    from adfeed.api import app
    client = TestClient(app)

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": "https://quota.myshopify.com/admin",
            "dest": "https://quota.myshopify.com",
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
    # Ensure store with tiny quota + access token
    client.get("/api/app/billing/status", headers={"Authorization": f"Bearer {token}"})
    store = store_db.get_store_by_domain("quota.myshopify.com")
    store_db.update_store(store.id, quota_total=2, quota_used=0, access_token="shpat_test")
    store_db.update_store(store.id, default_brand="Test Brand")

    from unittest.mock import AsyncMock, patch
    with patch(
        "adfeed.store_sync.sync_products_for_generate",
        new=AsyncMock(return_value=["p1", "p2", "p3"]),
    ):
        res = client.post(
            "/api/app/generate",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "product_ids": ["1", "2", "3"],
                "platforms": ["google", "meta"],
                "languages": ["US", "DE"],
            },
        )
    assert res.status_code == 402
    detail = res.json()["detail"]
    assert detail["estimate"] == 12
