"""Feed image picker — recommend, patch, feed resolution."""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def store_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()
    user = create_user(email=f"img-{uuid.uuid4().hex[:8]}@ex.com", name="Img")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:6]}.myshopify.com",
        quota_total=100,
    )
    return {"store_id": store.id, "store_db": store_db}


from adfeed.feed_image import (
    build_candidates,
    effective_feed_image,
    recommend_feed_image,
)
from adfeed import store_db


def test_recommend_prefers_non_risky_variant_default():
    candidates = build_candidates(
        product_image="https://img.1688.com/a.jpg",
        variant_image="https://cdn.shopify.com/v/red.jpg",
        shopify_images=["https://img.1688.com/a.jpg", "https://cdn.shopify.com/v/red.jpg"],
    )
    rec = recommend_feed_image(candidates)
    assert rec == "https://cdn.shopify.com/v/red.jpg"


def test_recommend_skips_risky_when_clean_exists():
    candidates = build_candidates(
        product_image="https://cbu01.alicdn.com/dirty.jpg",
        additional="https://cdn.shopify.com/s/files/clean.jpg",
    )
    rec = recommend_feed_image(candidates)
    assert "shopify.com" in rec
    assert "alicdn" not in rec


def test_effective_feed_image_override_wins():
    assert effective_feed_image(
        "https://cdn.shopify.com/override.jpg",
        "https://cdn.shopify.com/variant.jpg",
        "https://cdn.shopify.com/product.jpg",
    ) == "https://cdn.shopify.com/override.jpg"


def test_apply_feed_image_patch(store_env):
    store_id = store_env["store_id"]
    store_db = store_env["store_db"]
    product = store_db.save_product(store_id, title="Img Product", shopify_product_id="p-img")
    store_db.save_variant(
        product.id,
        "SKU-IMG-1",
        shopify_variant_id="9001",
        color="Red",
        image_url="https://cbu01.alicdn.com/old.jpg",
    )
    result = store_db.apply_feed_image_patches(store_id, [{
        "sku": "SKU-IMG-1",
        "image_url": "https://cdn.shopify.com/s/files/new.jpg",
    }])
    assert result["updated"] == ["SKU-IMG-1"]
    v = store_db.get_variant_by_sku_for_store(store_id, "SKU-IMG-1")
    assert v.feed_image_url == "https://cdn.shopify.com/s/files/new.jpg"
    assert v.image_url == "https://cbu01.alicdn.com/old.jpg"


def test_feed_quality_i03_on_risky_image():
    from adfeed.feed_quality import diagnose_row_basics

    events = diagnose_row_basics({
        "SKU": "x",
        "图片链接": "https://img.1688.com/foo.jpg",
        "优化后标题": "Test",
        "价格": 10,
        "链接": "https://shop.com/p",
    })
    assert any(e.rule_id == "I03" and e.level == "WARN" for e in events)
