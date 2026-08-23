"""Bulk patch Multicolor / One Size confirm → store_db."""
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def fresh_db(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]

    from adfeed.db import init_db, create_user

    init_db()
    from adfeed import store_db

    store_db.init_store_schema()
    user = create_user(email=f"test-{uuid.uuid4().hex[:8]}@example.com", name="Tester")
    return store_db, user


def _seed_variant(store_db, store_id: str, sku: str, color="Multicolor", size="One Size", shopify_pid=None):
    product = store_db.save_product(
        store_id,
        title="Tee",
        shopify_product_id=shopify_pid or f"gid://shopify/Product/{sku}",
    )
    return store_db.save_variant(
        product.id,
        sku,
        shopify_variant_id="41575567491130",
        title="Tee / M",
        color=color,
        size=size,
        price=19.99,
        inventory=3,
    )


def test_update_variant_attrs_scoped_to_store(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(user.id, "a.myshopify.com", access_token="t")
    other = store_db.create_store(user.id, "b.myshopify.com", access_token="t")
    _seed_variant(store_db, store.id, "SKU-A", color="Multicolor", size="One Size")
    _seed_variant(store_db, other.id, "SKU-B", color="Red", size="M")

    updated = store_db.update_variant_attrs_for_store(
        store.id, "SKU-A", color="Black", size="L"
    )
    assert updated is not None
    assert updated.color == "Black"
    assert updated.size == "L"
    assert updated.shopify_variant_id == "41575567491130"
    assert updated.price == 19.99

    # Cross-store SKU must not resolve
    assert store_db.get_variant_by_sku_for_store(other.id, "SKU-A") is None
    assert store_db.update_variant_attrs_for_store(other.id, "SKU-A", color="Green") is None
    assert store_db.get_variant_by_sku_for_store(other.id, "SKU-B").color == "Red"

    assert store_db.update_variant_attrs_for_store(store.id, "MISSING", color="Black") is None


def test_apply_variant_attr_patches(fresh_db):
    store_db, user = fresh_db
    store = store_db.create_store(user.id, "a.myshopify.com", access_token="t")
    _seed_variant(store_db, store.id, "S1")
    _seed_variant(store_db, store.id, "S2")

    result = store_db.apply_variant_attr_patches(
        store.id,
        [
            {"sku": "S1", "color": "Navy"},
            {"sku": "S2", "size": "XL"},
            {"sku": "NOPE", "color": "Black"},
            {"sku": "S1"},
        ],
    )
    assert result["updated"] == ["S1", "S2"]
    assert result["missing"] == ["NOPE"]
    assert store_db.get_variant_by_sku_for_store(store.id, "S1").color == "Navy"
    assert store_db.get_variant_by_sku_for_store(store.id, "S2").size == "XL"


def test_bulk_patch_and_regen_without_regenerate(fresh_db, monkeypatch):
    store_db, user = fresh_db
    from adfeed.quality_bulk import bulk_patch_and_regen

    store = store_db.create_store(user.id, "a.myshopify.com", access_token="t")
    _seed_variant(store_db, store.id, "S1", color="Multicolor")

    called = {"n": 0}

    def boom(*_a, **_k):
        called["n"] += 1
        raise AssertionError("should not regenerate")

    monkeypatch.setattr("adfeed.pipeline.generate_feed_for_store", boom)

    out = bulk_patch_and_regen(
        store.id,
        [{"sku": "S1", "color": "Black"}],
        regenerate=False,
    )
    assert out["updated"] == ["S1"]
    assert called["n"] == 0
    assert store_db.get_variant_by_sku_for_store(store.id, "S1").color == "Black"


def test_bulk_patch_and_regen_calls_pipeline(fresh_db, monkeypatch):
    store_db, user = fresh_db
    from adfeed.quality_bulk import bulk_patch_and_regen

    store = store_db.create_store(user.id, "a.myshopify.com", access_token="t")
    _seed_variant(store_db, store.id, "S1", color="Multicolor", size="One Size")

    def fake_gen(**kwargs):
        assert kwargs["store_id"] == store.id
        assert kwargs["countries"] == ["US"]
        assert kwargs["platforms"] == ["google"]
        return {
            "feed_urls": [{"platform": "google", "country": "US", "url": "https://x/us.xml", "items": 1}],
            "quality_report": {"light": "green", "summary": {"autofixed": 0}},
        }

    monkeypatch.setattr("adfeed.pipeline.generate_feed_for_store", fake_gen)

    out = bulk_patch_and_regen(
        store.id,
        [{"sku": "S1", "color": "Black", "size": "M"}],
        platforms=["google"],
        languages=["US"],
        regenerate=True,
    )
    assert out["updated"] == ["S1"]
    assert out["feeds"][0]["url"] == "https://x/us.xml"
    assert out["quality_report"]["light"] == "green"
    v = store_db.get_variant_by_sku_for_store(store.id, "S1")
    assert v.color == "Black" and v.size == "M"
