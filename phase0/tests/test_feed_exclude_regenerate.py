"""Remove-from-feed exclusions must clear when merchant re-generates those products."""
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

    from adfeed.db import init_db, create_user, _conn

    init_db()
    from adfeed import store_db

    store_db.init_store_schema()
    user = create_user(email=f"ex-{uuid.uuid4().hex[:8]}@example.com", name="Ex")
    store = store_db.create_store(
        user_id=user.id,
        shopify_domain=f"{uuid.uuid4().hex[:8]}.myshopify.com",
        shop_name="Demo",
        quota_total=50,
    )
    pid = str(uuid.uuid4())
    other_pid = str(uuid.uuid4())
    with _conn() as c:
        c.execute(
            """INSERT INTO products (id, store_id, title, status, feed_enabled, ai_status)
               VALUES (?, ?, 'Snowboard', 'active', 1, 'ready')""",
            (pid, store.id),
        )
        c.execute(
            """INSERT INTO products (id, store_id, title, status, feed_enabled, ai_status)
               VALUES (?, ?, 'Keep Out', 'active', 1, 'ready')""",
            (other_pid, store.id),
        )
        c.execute(
            """INSERT INTO product_variants
               (id, product_id, shopify_variant_id, sku, title, price, inventory, status)
               VALUES (?, ?, '111', 'sku-board-1', 'Black', 10, 5, 'active')""",
            (str(uuid.uuid4()), pid),
        )
        c.execute(
            """INSERT INTO product_variants
               (id, product_id, shopify_variant_id, sku, title, price, inventory, status)
               VALUES (?, ?, '222', 'sku-keep-out', 'X', 10, 5, 'active')""",
            (str(uuid.uuid4()), other_pid),
        )
        c.commit()
    return store_db, store, pid, other_pid


def test_remove_feed_excluded_skus(fresh_db):
    store_db, store, _pid, _other = fresh_db
    store_db.add_feed_excluded_skus(store.id, ["sku-board-1", "sku-keep-out"], "US", "google")
    assert "sku-board-1" in store_db.get_feed_excluded_skus(store.id, "US", "google")

    n = store_db.remove_feed_excluded_skus(store.id, ["sku-board-1"], "US", "google")
    assert n == 1
    left = store_db.get_feed_excluded_skus(store.id, "US", "google")
    assert "sku-board-1" not in left
    assert "sku-keep-out" in left


def test_clear_exclusions_when_merchant_regenerates_products(fresh_db):
    """Remove → exclude stays for merge of *other* products; re-generate *this* product clears it."""
    store_db, store, pid, other_pid = fresh_db
    store_db.add_feed_excluded_skus(
        store.id, ["sku-board-1", "sku-keep-out"], "US", "google"
    )

    cleared = store_db.clear_feed_exclusions_for_products(
        store.id,
        [pid],
        countries=["US"],
        platforms=["google"],
    )
    assert cleared >= 1
    left = store_db.get_feed_excluded_skus(store.id, "US", "google")
    assert "sku-board-1" not in left
    assert "sku-keep-out" in left
    assert other_pid  # sanity: other product still excluded via its sku
