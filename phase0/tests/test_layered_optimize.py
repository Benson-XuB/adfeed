"""Approach-3 layered optimize tests"""
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

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
    user = create_user(email=f"l-{uuid.uuid4().hex[:8]}@ex.com", name="L")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:6]}.myshopify.com",
        quota_total=100,
    )
    p1 = store_db.save_product(store.id, title="Blue Cotton Summer Dress", shopify_product_id="111")
    p2 = store_db.save_product(store.id, title="Red Silk Blouse", shopify_product_id="222")
    return store_db, store, [p1, p2]


def test_layered_writes_assets_and_debits(store_env):
    store_db, store, products = store_env
    from adfeed.pipeline import optimize_layered

    fake_multi = {
        "optimized_titles": {"US": "Summer Dress Blue Cotton", "DE": "Sommerkleid Blau"},
        "description_snippets": {"US": "Desc US", "DE": "Desc DE"},
        "ai_tags_by_lang": {"US": ["dress"], "DE": ["kleid"]},
    }

    with patch("adfeed.pipeline.load_gpc_taxonomy"), \
         patch("adfeed.pipeline.gpc_match", return_value={
             "gpc_code": "2271", "gpc_path": "Apparel > Dresses",
             "confidence": 0.9, "source": "test",
         }), \
         patch("adfeed.pipeline.optimize_multi_country", return_value=fake_multi), \
         patch("adfeed.pipeline.infer_product_attributes", return_value={
             "gender": "female", "age_group": "adult",
         }):
        result = optimize_layered(
            store_id=store.id,
            product_ids=[products[0].id, products[1].id],
            platforms=["google", "meta"],
            languages=["US", "DE"],
        )

    # 2 SKU × 2 platforms × 2 langs = 8
    assert result["ok_units"] == 8
    assert result["assets_written"] == 8
    refreshed = store_db.get_store(store.id)
    assert refreshed.quota_used == 8

    asset = store_db.get_product_asset_by_key(products[0].id, "meta", "US")
    assert asset is not None
    assert asset.title  # platform rewrite applied


def test_optimize_does_not_call_image_processor(store_env):
    store_db, store, products = store_env
    from adfeed.pipeline import optimize_layered

    fake_multi = {
        "optimized_titles": {"US": "Title"},
        "description_snippets": {"US": "D"},
        "ai_tags_by_lang": {"US": []},
    }

    with patch("adfeed.pipeline.load_gpc_taxonomy"), \
         patch("adfeed.pipeline.gpc_match", return_value={
             "gpc_code": "1", "gpc_path": "X", "confidence": 1, "source": "t",
         }), \
         patch("adfeed.pipeline.optimize_multi_country", return_value=fake_multi), \
         patch("adfeed.pipeline.infer_product_attributes", return_value={}), \
         patch("adfeed.image_processor.process_and_upload_image") as img:
        optimize_layered(
            store_id=store.id,
            product_ids=[products[0].id],
            platforms=["google"],
            languages=["US"],
        )
        img.assert_not_called()
