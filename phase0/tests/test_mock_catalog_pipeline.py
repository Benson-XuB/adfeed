"""Local mock catalog: multi-category seed + feed + GMC issues (no live Shopify)."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def mock_store(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.mock_catalog import (
        MOCK_AD_BRAND,
        MOCK_SHOP_DOMAIN,
        ensure_mock_store,
    )

    init_db()
    store_db.init_store_schema()
    store, seeded = ensure_mock_store(store_db, create_user=create_user)
    assert store.shopify_domain == MOCK_SHOP_DOMAIN
    assert store.default_brand == MOCK_AD_BRAND
    return store_db, store, seeded


def test_catalog_covers_many_types_and_pure_colors(mock_store):
    store_db, store, seeded = mock_store
    stats = seeded["stats"]
    assert stats["products"] >= 40
    assert stats["variants"] >= 100
    assert "Pants" in stats["product_types"]
    assert "Skirts" in stats["product_types"]
    assert "Jackets" in stats["product_types"]

    # color must stay pure — no Style/Floral stuffed into color field
    dirty = ("style", "floral", "print", "eprolo")
    for p in store_db.get_store_products(store.id):
        assert (p.brand or "").lower() != "eprolo"
        for v in store_db.get_product_variants(p.id):
            color = (v.color or "").strip().lower()
            if not color:
                continue
            assert not any(d in color for d in dirty), color
            assert v.barcode in (None, "")


def test_seed_is_idempotent(mock_store):
    store_db, store, seeded = mock_store
    from adfeed.mock_catalog import seed_mock_catalog

    again = seed_mock_catalog(store_db, store.id)
    assert len(again["skus"]) == len(seeded["skus"])
    assert len(store_db.get_store_products(store.id)) == seeded["stats"]["products"]


def test_optimize_generate_and_gmc_mock(mock_store):
    store_db, store, seeded = mock_store
    from adfeed.mock_catalog import MOCK_MERCHANT_ID, mock_gmc_issues
    from adfeed.pipeline import optimize_layered, generate_feed_for_store
    from adfeed.platforms.google.merchant_sync import sync_merchant_issues

    # Pants / skirt / jacket only — field-contract self-check trio
    handles = {
        "wide-leg-trousers",
        "midi-a-line-skirt",
        "classic-denim-jacket",
    }
    products = [
        p for p in store_db.get_store_products(store.id) if p.handle in handles
    ]
    assert len(products) == 3
    pids = [p.id for p in products]

    def _opt(*, original_title, countries, description="", **kwargs):
        return {
            "optimized_titles": {lang: original_title for lang in countries},
            "description_snippets": {
                lang: (description or original_title)[:120] for lang in countries
            },
            "ai_tags_by_lang": {lang: [] for lang in countries},
        }

    with patch("adfeed.pipeline.load_gpc_taxonomy"), patch(
        "adfeed.pipeline.gpc_match",
        return_value={
            "gpc_code": "2271",
            "gpc_path": "Apparel & Accessories > Clothing",
            "confidence": 0.95,
            "source": "mock",
        },
    ), patch("adfeed.pipeline.optimize_multi_country", side_effect=_opt), patch(
        "adfeed.pipeline.infer_product_attributes",
        return_value={},
    ):
        opt = optimize_layered(
            store_id=store.id,
            product_ids=pids,
            platforms=["google"],
            languages=["US"],
        )
    assert opt["ok_units"] == 3
    assert opt["assets_written"] == 3

    feeds = generate_feed_for_store(
        store.id,
        countries=["US"],
        platforms=["google"],
        product_ids=pids,
    )
    assert feeds
    # titles stay short / human (product title, not attribute wall)
    for p in products:
        asset = store_db.get_product_asset_by_key(p.id, "google", "US")
        assert asset and asset.title
        assert len(asset.title) < 80
        assert "eprolo" not in asset.title.lower()

    from adfeed.platforms.common.issue_actions import suggest_action

    class _Mock:
        def list_product_issues(self, merchant_id: str):
            return mock_gmc_issues()

    store_db.upsert_google_merchant_account(store.id, MOCK_MERCHANT_ID, select=True)
    result = sync_merchant_issues(store.id, MOCK_MERCHANT_ID, _Mock())
    assert result["matched"] >= 3
    assert result["unmatched"] >= 3
    rows = store_db.list_gmc_product_issues(store.id, MOCK_MERCHANT_ID)
    by_oid = {r["offer_id"]: r for r in rows}
    assert suggest_action(by_oid["NL-GAP-SOCK-OS"]["reason_code"])["action"] == "pick_feed_image"
    assert suggest_action(by_oid["NL-GAP-TEE-M"]["reason_code"])["action"] == "edit_color_size"
    assert suggest_action(by_oid["NL-JKT-BLU-M"]["reason_code"])["action"] == "confirm_brand"
    assert by_oid["UNKNOWN-OFFER-999"]["product_id_internal"] is None


def test_api_google_issues_sync_accepts_mock_without_oauth(monkeypatch, tmp_path):
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

    import time
    import jwt
    from fastapi.testclient import TestClient
    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.mock_catalog import (
        MOCK_MERCHANT_ID,
        MOCK_SHOP_DOMAIN,
        ensure_mock_store,
        mock_gmc_issues,
    )
    from adfeed.api import app

    init_db()
    store_db.init_store_schema()
    store, _ = ensure_mock_store(store_db, create_user=create_user)
    client = TestClient(app)

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": f"https://{MOCK_SHOP_DOMAIN}/admin",
            "dest": f"https://{MOCK_SHOP_DOMAIN}",
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
    res = client.post(
        "/api/app/google/issues/sync",
        headers={"Authorization": f"Bearer {token}"},
        json={"merchant_id": MOCK_MERCHANT_ID, "mock_issues": mock_gmc_issues()},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["matched"] >= 3
    assert body["unmatched"] >= 3
