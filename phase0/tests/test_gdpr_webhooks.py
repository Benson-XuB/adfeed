"""GDPR / shop redact webhooks — required for public App Store review."""
import base64
import hashlib
import hmac
import json
import sys
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SECRET = "test-client-secret"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


@pytest.fixture()
def gdpr_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", SECRET)
    monkeypatch.delenv("ADFEED_WEBHOOK_SKIP_HMAC", raising=False)
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    import adfeed.config as cfg
    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = SECRET

    from adfeed.db import init_db, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    from adfeed.api import app

    user = create_user(email=f"gdpr-{uuid.uuid4().hex[:8]}@ex.com", name="GDPR")
    return TestClient(app), store_db, user, tmp_path


def _post(client, path, body: dict, topic: str, shop: str, hmac_header: str | None = None):
    raw = json.dumps(body).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Topic": topic,
        "X-Shopify-Shop-Domain": shop,
    }
    if hmac_header is None:
        headers["X-Shopify-Hmac-Sha256"] = _sign(raw)
    elif hmac_header:
        headers["X-Shopify-Hmac-Sha256"] = hmac_header
    return client.post(path, content=raw, headers=headers)


def test_invalid_hmac_returns_401_when_secret_set(gdpr_env):
    client, _, _, _ = gdpr_env
    res = _post(
        client,
        "/api/webhooks/shopify/shop_redact",
        {"shop_id": 1, "shop_domain": "gone.myshopify.com"},
        "shop/redact",
        "gone.myshopify.com",
        hmac_header="not-a-valid-hmac",
    )
    assert res.status_code == 401


def test_shop_redact_deletes_store_products_and_feed_files(gdpr_env):
    client, store_db, user, tmp_path = gdpr_env
    shop = f"{uuid.uuid4().hex[:8]}.myshopify.com"
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=shop,
        shop_name="Wipe Me",
        access_token="shpat_test",
    )
    product = store_db.save_product(store.id, "Sock", shopify_product_id="111")
    store_db.save_variant(product.id, f"SKU-{uuid.uuid4().hex[:8]}", title="White / OS")
    store_db.create_store_job(store.id, ["google"], ["US"], [product.id])
    store_db.record_usage(store.id, "google", "US", sku="SKU1")

    feed_dir = tmp_path / "feeds" / store.id / "google"
    feed_dir.mkdir(parents=True)
    feed_path = feed_dir / "us.xml"
    feed_path.write_text("<rss/>", encoding="utf-8")
    store_db.save_feed_file(
        store.id, "US", str(feed_path), "https://example.com/us.xml", item_count=1
    )

    other_shop = f"{uuid.uuid4().hex[:8]}.myshopify.com"
    other = store_db.create_store(user_id=user.id, shopify_domain=other_shop)

    res = _post(
        client,
        "/api/webhooks/shopify/shop_redact",
        {"shop_id": 9, "shop_domain": shop},
        "shop/redact",
        shop,
    )
    assert res.status_code == 200
    assert res.json().get("ok") is True
    assert store_db.get_store_by_domain(shop) is None
    assert store_db.get_store(store.id) is None
    assert store_db.get_store_products(store.id) == []
    assert store_db.get_store(other.id) is not None
    assert not feed_path.exists()


def test_customers_redact_acks_without_customer_pii(gdpr_env):
    client, _, _, _ = gdpr_env
    res = _post(
        client,
        "/api/webhooks/shopify/customers_redact",
        {
            "shop_id": 1,
            "shop_domain": "x.myshopify.com",
            "customer": {"id": 191167, "email": "john@example.com"},
            "orders_to_redact": [1],
        },
        "customers/redact",
        "x.myshopify.com",
    )
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True
    assert data.get("stored_customer_pii") is False


def test_shop_redact_unknown_shop_still_200(gdpr_env):
    client, _, _, _ = gdpr_env
    res = _post(
        client,
        "/api/webhooks/shopify/shop_redact",
        {"shop_id": 1, "shop_domain": "missing.myshopify.com"},
        "shop/redact",
        "missing.myshopify.com",
    )
    assert res.status_code == 200
    assert res.json().get("ok") is True


def test_unified_compliance_uri_dispatches_shop_redact(gdpr_env):
    client, store_db, user, _ = gdpr_env
    shop = f"{uuid.uuid4().hex[:8]}.myshopify.com"
    store_db.create_store(user_id=user.id, shopify_domain=shop)
    res = _post(
        client,
        "/api/webhooks/shopify/compliance",
        {"shop_id": 2, "shop_domain": shop},
        "shop/redact",
        shop,
    )
    assert res.status_code == 200
    assert store_db.get_store_by_domain(shop) is None
