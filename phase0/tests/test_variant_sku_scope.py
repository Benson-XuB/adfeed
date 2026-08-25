"""Variant SKU scoping — duplicate SKUs across products must not steal rows."""
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
    user = create_user(email=f"sku-{uuid.uuid4().hex[:8]}@ex.com", name="Sku")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:6]}.myshopify.com",
        quota_total=100,
    )
    return {"store_id": store.id, "store_db": store_db}


def test_duplicate_sku_across_products_keeps_both(store_env):
    store_db = store_env["store_db"]
    sid = store_env["store_id"]
    active = store_db.save_product(sid, title="Socks active", status="active")
    draft = store_db.save_product(sid, title="Socks draft", status="disabled")

    shared_sku = "6056210940851"
    store_db.save_variant(
        active.id,
        shared_sku,
        shopify_variant_id="111",
        title="Black / M",
        price=10,
    )
    store_db.save_variant(
        draft.id,
        shared_sku,
        shopify_variant_id="222",
        title="Black / M",
        price=10,
    )

    active_vars = store_db.get_product_variants(active.id)
    draft_vars = store_db.get_product_variants(draft.id)
    assert len(active_vars) == 1
    assert len(draft_vars) == 1
    assert active_vars[0].sku == shared_sku
    assert draft_vars[0].sku == shared_sku
    assert active_vars[0].id != draft_vars[0].id
    assert active_vars[0].shopify_variant_id == "111"
    assert draft_vars[0].shopify_variant_id == "222"
