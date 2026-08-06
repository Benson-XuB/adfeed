"""store_sync: ID normalize + upsert products"""
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    user = create_user(email=f"s-{uuid.uuid4().hex[:8]}@ex.com", name="S")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain="sync.myshopify.com",
        access_token="shpat_test",
        quota_total=100,
    )
    return store_db, store


def test_normalize_gid():
    from adfeed.store_sync import normalize_shopify_product_id
    assert normalize_shopify_product_id("gid://shopify/Product/12345") == "12345"
    assert normalize_shopify_product_id("12345") == "12345"
    assert normalize_shopify_product_id(" 99 ") == "99"


def test_upsert_raw_product_with_variants(env):
    store_db, store = env
    from adfeed.store_sync import upsert_raw_shopify_product

    raw = {
        "id": 111,
        "title": "Blue Dress",
        "handle": "blue-dress",
        "vendor": "BrandX",
        "product_type": "Dress",
        "status": "active",
        "body_html": "<p>Nice dress</p>",
        "options": [
            {"name": "Color", "position": 1},
            {"name": "Size", "position": 2},
        ],
        "images": [{"id": 1, "src": "https://cdn.example/a.jpg"}],
        "variants": [
            {
                "id": 201,
                "sku": "DRESS-S",
                "title": "Blue / S",
                "option1": "Blue",
                "option2": "S",
                "price": "29.99",
                "inventory_quantity": 5,
                "image_id": 1,
            },
            {
                "id": 202,
                "sku": "DRESS-M",
                "title": "Blue / M",
                "option1": "Blue",
                "option2": "M",
                "price": "29.99",
                "inventory_quantity": 3,
            },
        ],
    }
    saved = upsert_raw_shopify_product(store.id, raw)
    assert saved.shopify_product_id == "111"
    assert saved.title == "Blue Dress"
    variants = store_db.get_product_variants(saved.id)
    assert len(variants) == 2
    assert {v.sku for v in variants} == {"DRESS-S", "DRESS-M"}
    assert any(v.color == "Blue" and v.size == "S" for v in variants)


def test_sync_products_for_generate(env):
    import asyncio
    store_db, store = env
    from adfeed.store_sync import sync_products_for_generate

    raw = {
        "id": 555,
        "title": "Tee",
        "handle": "tee",
        "vendor": "V",
        "product_type": "Top",
        "status": "active",
        "body_html": "",
        "options": [],
        "images": [],
        "variants": [
            {"id": 1, "sku": "TEE-1", "title": "Default", "price": "10", "inventory_quantity": 1},
        ],
    }
    with patch(
        "adfeed.store_sync.fetch_raw_product",
        new=AsyncMock(return_value=raw),
    ):
        ids = asyncio.get_event_loop().run_until_complete(
            sync_products_for_generate(store, ["gid://shopify/Product/555"])
        )
    assert len(ids) == 1
    p = store_db.get_product(ids[0])
    assert p.shopify_product_id == "555"
