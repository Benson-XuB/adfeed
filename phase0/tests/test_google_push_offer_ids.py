"""Push without rows uses same offerId as Google XML g:id (SKU)."""
from __future__ import annotations

import re
import sys
import time
import uuid
from pathlib import Path
from unittest.mock import patch

import jwt
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SHOP = "push-offer.myshopify.com"
MERCHANT_ID = "55555"
DATA_SOURCE = "accounts/55555/dataSources/api-primary"
SKU = "NL-PUSH-TEE-M"


@pytest.fixture()
def client_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("SHOPIFY_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("SHOPIFY_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://example.test")
    monkeypatch.setenv("GOOGLE_PUSH_ENABLED", "1")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    import adfeed.config as cfg

    cfg.SHOPIFY_CLIENT_ID = "test-client-id"
    cfg.SHOPIFY_CLIENT_SECRET = "test-client-secret"
    cfg.PUBLIC_BASE_URL = "https://example.test"
    cfg.WEB_SAAS_ENABLED = False
    cfg.FEEDS_DIR = tmp_path / "feeds"
    cfg.FEEDS_DIR.mkdir(parents=True, exist_ok=True)

    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.api import app

    init_db()
    store_db.init_store_schema()
    user = create_user(email=f"offer-{uuid.uuid4().hex[:8]}@ex.com", name="Offer")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=SHOP,
        shop_name="Offer Shop",
    )
    store_db.update_store(store.id, default_currency="USD", default_brand="Northline")
    store = store_db.get_store(store.id)
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


def _seed_ready_product(store_db, store):
    product = store_db.save_product(
        store.id,
        title="Push Tee",
        shopify_product_id="9001",
        handle="push-tee",
        brand="Northline",
        optimized_title="Push Tee",
        image_url="https://example.com/tee.jpg",
        description="A simple tee",
        gpc_code="212",
        gpc_path="Apparel & Accessories > Clothing > Shirts & Tops",
        feed_enabled=1,
        ai_status="ready",
        status="active",
    )
    store_db.save_variant(
        product.id,
        SKU,
        shopify_variant_id="9001001",
        title="M / White",
        color="White",
        size="M",
        price=19.0,
        inventory=3,
        image_url="https://example.com/tee.jpg",
    )
    return product


def test_google_push_uses_same_offer_ids_as_xml(client_env, monkeypatch):
    client, store_db, store = client_env
    _seed_ready_product(store_db, store)
    store_db.upsert_google_merchant_account(store.id, MERCHANT_ID, "MC", select=True)
    store_db.set_merchant_data_source(store.id, MERCHANT_ID, DATA_SOURCE)

    from adfeed.pipeline import build_feed_rows_for_store, generate_feed_for_store
    from adfeed.platforms.google.product_mapper import map_row_to_product_input

    # Avoid live Shopify currency refresh in tests
    with patch(
        "adfeed.store_sync.refresh_store_currency_from_shopify",
        side_effect=lambda s: s,
    ):
        rows = build_feed_rows_for_store(store.id, country="US")
        xml_result = generate_feed_for_store(
            store.id,
            countries=["US"],
            platforms=["google"],
        )

    assert rows, "expected canonical rows from store"
    mapped = map_row_to_product_input(rows[0], feed_label="US")
    assert mapped["offerId"] == SKU

    assert xml_result.get("feed_urls")
    from adfeed.config import FEEDS_DIR
    from adfeed.platforms.common.paths import durable_feed_path

    xml_path = durable_feed_path(FEEDS_DIR, store.id, "google", "US")
    xml = xml_path.read_text(encoding="utf-8")
    ids = {i.replace(" ", "-") for i in re.findall(r"<g:id>(.*?)</g:id>", xml)}
    assert mapped["offerId"] in ids
    assert SKU in ids

    # API path: omit rows → build from store → push Fake
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"use_fake": True, "feed_label": "US"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["ok_count"] >= 1
    items = store_db.list_push_items(body["id"])
    offer_ids = {i["offer_id"] for i in items}
    assert SKU in offer_ids


def test_push_empty_catalog_without_rows_returns_400(client_env):
    client, store_db, store = client_env
    store_db.upsert_google_merchant_account(store.id, MERCHANT_ID, "MC", select=True)
    store_db.set_merchant_data_source(store.id, MERCHANT_ID, DATA_SOURCE)
    res = client.post(
        "/api/app/google/push",
        headers=_auth_headers(),
        json={"use_fake": True},
    )
    assert res.status_code == 400
    assert "row" in res.json()["detail"].lower() or "feed" in res.json()["detail"].lower()
