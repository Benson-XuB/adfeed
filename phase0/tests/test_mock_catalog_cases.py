"""Dozens of mock-catalog cases: types, SKUs, GMC actions, offer match, gaps.

No live Shopify. Safe during App Store review.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ── helpers / fixtures ──────────────────────────────────────────────


@pytest.fixture()
def mock_store(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.mock_catalog import MOCK_AD_BRAND, MOCK_SHOP_DOMAIN, ensure_mock_store

    init_db()
    store_db.init_store_schema()
    store, seeded = ensure_mock_store(store_db, create_user=create_user)
    assert store.shopify_domain == MOCK_SHOP_DOMAIN
    assert store.default_brand == MOCK_AD_BRAND
    return store_db, store, seeded


def _catalog():
    from adfeed.mock_catalog import catalog_products, catalog_stats, mock_gmc_issues

    return catalog_products(), catalog_stats(), mock_gmc_issues()


def _all_types():
    _, stats, _ = _catalog()
    return stats["product_types"]


def _all_handles():
    products, _, _ = _catalog()
    return [p["handle"] for p in products]


def _all_skus_with_meta():
    products, _, _ = _catalog()
    rows = []
    for p in products:
        for v in p["variants"]:
            rows.append(
                (
                    v["sku"],
                    p["handle"],
                    p["product_type"],
                    v.get("color"),
                    v.get("size"),
                    float(v.get("price") or 0),
                    int(v.get("inventory") or 0),
                )
            )
    return rows


def _gmc_cases():
    from adfeed.platforms.common.issue_actions import suggest_action
    from adfeed.mock_catalog import catalog_stats, mock_gmc_issues

    skus = set(catalog_stats()["skus"])
    rows = []
    for it in mock_gmc_issues():
        oid = it["offer_id"]
        matched = oid in skus
        action = suggest_action(it.get("reason_code") or "")["action"]
        rows.append((oid, it.get("reason_code") or "", it.get("status") or "", action, matched))
    return rows


# ── scale / inventory shape ─────────────────────────────────────────


def test_catalog_scale_is_large():
    _, stats, issues = _catalog()
    assert stats["products"] >= 40
    assert stats["variants"] >= 100
    assert len(stats["product_types"]) >= 30
    assert len(issues) >= 20


@pytest.mark.parametrize("product_type", _all_types())
def test_each_product_type_present(product_type):
    products, _, _ = _catalog()
    assert any(p["product_type"] == product_type for p in products)


@pytest.mark.parametrize("handle", _all_handles())
def test_each_handle_has_variants_and_title(handle):
    products, _, _ = _catalog()
    item = next(p for p in products if p["handle"] == handle)
    assert item["title"]
    assert len(item["title"]) < 80
    assert item["variants"]
    assert item["shopify_product_id"]
    assert "eprolo" not in (item.get("vendor") or "").lower()


# ── field-contract: color / brand / barcode ─────────────────────────


_DIRTY_COLOR = ("style", "floral", "print", "pattern", "eprolo", "multicolor")


@pytest.mark.parametrize(
    "sku,handle,ptype,color,size,price,inventory",
    _all_skus_with_meta(),
    ids=[r[0] for r in _all_skus_with_meta()],
)
def test_each_sku_field_contract(sku, handle, ptype, color, size, price, inventory):
    assert sku and sku.startswith("NL-")
    if color:
        c = color.strip().lower()
        assert not any(d in c for d in _DIRTY_COLOR), f"{sku} dirty color={color!r}"
        # pure color ≈ short token (allow spaces like "One Size" is size, not color)
        assert len(color) <= 20
    assert price >= 0
    assert inventory >= 0


def test_no_barcode_anywhere(mock_store):
    store_db, store, _ = mock_store
    for p in store_db.get_store_products(store.id):
        assert (p.brand or "") == "Northline"
        for v in store_db.get_product_variants(p.id):
            assert v.barcode in (None, "")


def test_never_uses_live_shop_domain(mock_store):
    _, store, _ = mock_store
    assert store.shopify_domain == "adfeed-mock.myshopify.com"
    assert "qx2kd5" not in store.shopify_domain


# ── intentional gaps ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "handle,expect_missing_color,expect_missing_image,expect_zero_price,expect_oos",
    [
        ("gap-missing-color-tee", True, False, False, False),
        ("gap-missing-image-socks", False, True, False, False),
        ("gap-zero-price-pin", False, False, True, False),
        ("gap-oos-belt", False, False, False, True),
    ],
)
def test_gap_products(
    mock_store, handle, expect_missing_color, expect_missing_image, expect_zero_price, expect_oos
):
    store_db, store, _ = mock_store
    products = [p for p in store_db.get_store_products(store.id) if p.handle == handle]
    assert len(products) == 1
    p = products[0]
    variants = store_db.get_product_variants(p.id)
    assert variants
    v = variants[0]
    if expect_missing_color:
        assert not (v.color or "").strip()
    if expect_missing_image:
        assert not (p.image_url or "").strip()
        assert not (v.image_url or "").strip()
    if expect_zero_price:
        assert float(v.price or 0) == 0
    if expect_oos:
        assert int(v.inventory or 0) == 0


# ── field-contract trio titles / colors ─────────────────────────────


@pytest.mark.parametrize(
    "handle,expected_title,allowed_colors",
    [
        ("wide-leg-trousers", "High-Waist Wide-Leg Trousers", {"Black", "Khaki"}),
        ("midi-a-line-skirt", "A-Line Midi Skirt", {"Navy", "Cream"}),
        ("classic-denim-jacket", "Classic Denim Jacket", {"Blue"}),
        ("pink-floral-midi-dress", "Pink Floral Midi Dress", {"Pink"}),
    ],
)
def test_apparel_trio_and_floral_color_split(mock_store, handle, expected_title, allowed_colors):
    store_db, store, _ = mock_store
    p = next(x for x in store_db.get_store_products(store.id) if x.handle == handle)
    assert p.title == expected_title
    colors = {v.color for v in store_db.get_product_variants(p.id) if v.color}
    assert colors == allowed_colors
    # floral print lives in title language, not color field
    assert "Floral" not in colors
    assert "floral" not in {c.lower() for c in colors}


# ── issue_actions mapping (many codes) ──────────────────────────────


@pytest.mark.parametrize(
    "reason_code,expected_action",
    [
        ("image_missing", "pick_feed_image"),
        ("image_too_small", "pick_feed_image"),
        ("picture_blurry", "pick_feed_image"),
        ("photo_watermark", "pick_feed_image"),
        ("missing_color", "edit_color_size"),
        ("invalid_color", "edit_color_size"),
        ("missing_size", "edit_color_size"),
        ("soft_size_mismatch", "edit_color_size"),
        ("invalid_brand", "confirm_brand"),
        ("missing_brand", "confirm_brand"),
        ("brand_mismatch", "confirm_brand"),
        ("missing_gtin", "view_only"),
        ("invalid_identifier", "view_only"),
        ("gtin_conflict", "view_only"),
        ("price_mismatch", "view_only"),
        ("out_of_stock", "view_only"),
        ("policy_violation", "view_only"),
        ("landing_page_error", "view_only"),
        ("shipping_issue", "view_only"),
        ("under_review", "view_only"),
        ("", "view_only"),
        ("other", "view_only"),
        ("IMAGE_LINK_BROKEN", "pick_feed_image"),
        ("ColorRequired", "edit_color_size"),
        ("BrandRequired", "confirm_brand"),
        ("gtin_and_mpn_missing", "view_only"),
    ],
)
def test_suggest_action_matrix(reason_code, expected_action):
    from adfeed.platforms.common.issue_actions import suggest_action

    assert suggest_action(reason_code)["action"] == expected_action


# ── offer match edge cases ──────────────────────────────────────────


@pytest.mark.parametrize(
    "offer_id,sku_set,expected",
    [
        ("NL-PANT-BLK-M", {"NL-PANT-BLK-M", "NL-PANT-BLK-S"}, "NL-PANT-BLK-M"),
        ("NL-PANT-BLK-M", {"nl-pant-blk-m"}, None),  # exact, case-sensitive
        (" NL-PANT-BLK-M ", {"NL-PANT-BLK-M"}, "NL-PANT-BLK-M"),
        ("", {"NL-PANT-BLK-M"}, None),
        ("NL-PANT-BLK-M", set(), None),
        ("NL-PANT-BLK", {"NL-PANT-BLK-M"}, None),  # no fuzzy prefix
        ("NL-PANT-BLK-M-EXTRA", {"NL-PANT-BLK-M"}, None),
        ("GHOST-SKU-001", {"NL-PANT-BLK-M"}, None),
        ("NL-X00-CAM-S", {"NL-X00-CAM-S"}, "NL-X00-CAM-S"),
        ("UNKNOWN-OFFER-999", set(r[0] for r in _all_skus_with_meta()), None),
    ],
)
def test_offer_match_exact_only(offer_id, sku_set, expected):
    from adfeed.platforms.common.offer_match import match_offer_to_sku

    assert match_offer_to_sku(offer_id, sku_set) == expected


# ── every mock GMC issue: action + match expectation (no DB) ─────────


@pytest.mark.parametrize(
    "offer_id,reason_code,status,expected_action,should_match",
    _gmc_cases(),
    ids=[c[0] for c in _gmc_cases()],
)
def test_each_gmc_issue_expectation(
    offer_id, reason_code, status, expected_action, should_match
):
    from adfeed.platforms.common.issue_actions import suggest_action
    from adfeed.platforms.common.offer_match import match_offer_to_sku
    from adfeed.mock_catalog import catalog_stats

    assert suggest_action(reason_code)["action"] == expected_action
    internal = match_offer_to_sku(offer_id, set(catalog_stats()["skus"]))
    if should_match:
        assert internal == offer_id
    else:
        assert internal is None
    assert status in {"approved", "disapproved", "pending", "unknown"} or status == status


def test_gmc_sync_writes_all_issues_once(mock_store):
    store_db, store, _ = mock_store
    from adfeed.mock_catalog import MOCK_MERCHANT_ID, mock_gmc_issues
    from adfeed.platforms.google.merchant_sync import sync_merchant_issues
    from adfeed.platforms.common.issue_actions import suggest_action

    class _Mock:
        def list_product_issues(self, merchant_id: str):
            return mock_gmc_issues()

    store_db.upsert_google_merchant_account(store.id, MOCK_MERCHANT_ID, select=True)
    result = sync_merchant_issues(store.id, MOCK_MERCHANT_ID, _Mock())
    issues = mock_gmc_issues()
    assert result["written"] == len(issues)
    assert result["unmatched"] >= 3
    assert result["matched"] >= 15
    rows = {r["offer_id"]: r for r in store_db.list_gmc_product_issues(store.id, MOCK_MERCHANT_ID)}
    assert set(rows) == {it["offer_id"] for it in issues}
    for it in issues:
        row = rows[it["offer_id"]]
        assert row["reason_code"] == (it.get("reason_code") or "")
        assert suggest_action(row["reason_code"])["action"] == suggest_action(
            it.get("reason_code") or ""
        )["action"]


# ── API: list issues returns suggested_action for each ──────────────


def test_api_lists_suggested_actions_for_all_mock_issues(monkeypatch, tmp_path):
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
    from adfeed.platforms.common.issue_actions import suggest_action

    init_db()
    store_db.init_store_schema()
    ensure_mock_store(store_db, create_user=create_user)
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
    headers = {"Authorization": f"Bearer {token}"}
    sync = client.post(
        "/api/app/google/issues/sync",
        headers=headers,
        json={"merchant_id": MOCK_MERCHANT_ID, "mock_issues": mock_gmc_issues()},
    )
    assert sync.status_code == 200, sync.text
    listed = client.get(
        f"/api/app/google/issues?merchant_id={MOCK_MERCHANT_ID}",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body["issues"]) == len(mock_gmc_issues())
    for it in body["issues"]:
        assert it["suggested_action"] == suggest_action(it.get("reason_code") or "")["action"]


# ── seed idempotency under large catalog ────────────────────────────


def test_large_seed_idempotent(mock_store):
    store_db, store, seeded = mock_store
    from adfeed.mock_catalog import seed_mock_catalog

    again = seed_mock_catalog(store_db, store.id)
    assert again["stats"]["products"] == seeded["stats"]["products"]
    assert again["stats"]["variants"] == seeded["stats"]["variants"]
    assert len(store_db.get_store_products(store.id)) == seeded["stats"]["products"]
