"""Mock catalog Meta + TikTok feeds and issue sync (no live Shopify)."""
from __future__ import annotations

import csv
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture()
def mock_store(monkeypatch, tmp_path):
    monkeypatch.setenv("ADFEED_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("ADFEED_PUBLIC_URL", "https://example.test")
    for name in list(sys.modules):
        if name == "adfeed" or name.startswith("adfeed."):
            del sys.modules[name]
    from adfeed.db import init_db, create_user
    from adfeed import store_db
    from adfeed.mock_catalog import ensure_mock_store

    init_db()
    store_db.init_store_schema()
    store, seeded = ensure_mock_store(store_db, create_user=create_user)
    return store_db, store, seeded


def _opt(*, original_title, countries, description="", **kwargs):
    return {
        "optimized_titles": {lang: original_title for lang in countries},
        "description_snippets": {
            lang: (description or original_title)[:120] for lang in countries
        },
        "ai_tags_by_lang": {lang: [] for lang in countries},
    }


def _optimize_and_generate(store_db, store, product_ids, platforms):
    from adfeed.pipeline import optimize_layered, generate_feed_for_store

    with patch("adfeed.pipeline.load_gpc_taxonomy"), patch(
        "adfeed.pipeline.gpc_match",
        return_value={
            "gpc_code": "2271",
            "gpc_path": "Apparel & Accessories > Clothing > Dresses",
            "confidence": 0.95,
            "source": "mock",
        },
    ), patch("adfeed.pipeline.optimize_multi_country", side_effect=_opt), patch(
        "adfeed.pipeline.infer_product_attributes",
        return_value={},
    ):
        opt = optimize_layered(
            store_id=store.id,
            product_ids=product_ids,
            platforms=platforms,
            languages=["US"],
        )
    feeds = generate_feed_for_store(
        store.id,
        countries=["US"],
        platforms=platforms,
        product_ids=product_ids,
    )
    return opt, feeds


def test_generate_meta_and_tiktok_feeds(mock_store):
    store_db, store, seeded = mock_store
    handles = {"wide-leg-trousers", "midi-a-line-skirt", "classic-denim-jacket"}
    products = [p for p in store_db.get_store_products(store.id) if p.handle in handles]
    assert len(products) == 3
    pids = [p.id for p in products]

    opt, feeds = _optimize_and_generate(
        store_db, store, pids, ["google", "meta", "tiktok"]
    )
    # 3 products × 3 platforms × 1 lang
    assert opt["ok_units"] == 9
    assert opt["assets_written"] == 9

    urls = {(u["platform"], u["country"]): u for u in feeds["feed_urls"]}
    assert ("google", "US") in urls or ("google", "us") in {
        (k[0], k[1].upper()) for k in urls
    }
    platforms_seen = {u["platform"] for u in feeds["feed_urls"]}
    assert "google" in platforms_seen
    assert "meta" in platforms_seen
    assert "tiktok" in platforms_seen
    assert feeds["total_items"] >= 9

    for p in products:
        for plat in ("google", "meta", "tiktok"):
            asset = store_db.get_product_asset_by_key(p.id, plat, "US")
            assert asset and asset.title
            assert "eprolo" not in asset.title.lower()


def test_meta_issues_sync_mock(mock_store):
    store_db, store, _ = mock_store
    from adfeed.mock_catalog import MOCK_META_CATALOG_ID, mock_meta_issues
    from adfeed.platforms.meta.issues_sync import sync_meta_issues
    from adfeed.platforms.common.issue_actions import suggest_action

    class _Mock:
        def list_product_issues(self, catalog_id: str):
            return mock_meta_issues()

    result = sync_meta_issues(store.id, MOCK_META_CATALOG_ID, _Mock())
    assert result["written"] == len(mock_meta_issues())
    assert result["matched"] >= 8
    assert result["unmatched"] >= 2
    rows = {r["offer_id"]: r for r in store_db.list_meta_product_issues(store.id, MOCK_META_CATALOG_ID)}
    assert suggest_action(rows["NL-GAP-SOCK-OS"]["reason_code"])["action"] == "pick_feed_image"
    assert suggest_action(rows["NL-GAP-TEE-M"]["reason_code"])["action"] == "edit_color_size"
    assert suggest_action(rows["NL-JKT-BLU-M"]["reason_code"])["action"] == "confirm_brand"
    assert not rows["META-GHOST-001"]["product_id_internal"]


def test_tiktok_issues_sync_mock(mock_store):
    store_db, store, _ = mock_store
    from adfeed.mock_catalog import MOCK_TIKTOK_SHOP_ID, mock_tiktok_issues
    from adfeed.platforms.tiktok.issues_sync import sync_tiktok_issues
    from adfeed.platforms.common.issue_actions import suggest_action

    class _Mock:
        def list_product_issues(self, shop_id: str):
            return mock_tiktok_issues()

    result = sync_tiktok_issues(store.id, MOCK_TIKTOK_SHOP_ID, _Mock())
    assert result["written"] == len(mock_tiktok_issues())
    assert result["matched"] >= 8
    assert result["unmatched"] >= 2
    rows = {
        r["offer_id"]: r
        for r in store_db.list_tiktok_product_issues(store.id, MOCK_TIKTOK_SHOP_ID)
    }
    assert suggest_action(rows["NL-GAP-SOCK-OS"]["reason_code"])["action"] == "pick_feed_image"
    assert suggest_action(rows["NL-JKT-BLU-M"]["reason_code"])["action"] == "confirm_brand"
    assert suggest_action(rows["NL-SNK-WHT-38"]["reason_code"])["action"] == "view_only"
    assert not rows["TT-GHOST-001"]["product_id_internal"]


@pytest.mark.parametrize(
    "offer_id,expected_action,should_match",
    [
        ("NL-GAP-SOCK-OS", "pick_feed_image", True),
        ("NL-GAP-TEE-M", "edit_color_size", True),
        ("NL-JKT-BLU-M", "confirm_brand", True),
        ("NL-BAG-BRN-OS", "view_only", True),
        ("NL-DRS-PNK-M", "pick_feed_image", True),
        ("NL-X04-BLA-S", "edit_color_size", True),
        ("META-GHOST-001", "view_only", False),
        ("META-GHOST-002", "edit_color_size", False),
    ],
)
def test_each_meta_issue_expectation(offer_id, expected_action, should_match):
    from adfeed.mock_catalog import catalog_stats, mock_meta_issues
    from adfeed.platforms.common.issue_actions import suggest_action
    from adfeed.platforms.common.offer_match import match_offer_to_sku

    issue = next(i for i in mock_meta_issues() if i["offer_id"] == offer_id)
    assert suggest_action(issue["reason_code"])["action"] == expected_action
    internal = match_offer_to_sku(offer_id, set(catalog_stats()["skus"]))
    assert (internal == offer_id) is should_match


@pytest.mark.parametrize(
    "offer_id,expected_action,should_match",
    [
        ("NL-GAP-SOCK-OS", "pick_feed_image", True),
        ("NL-GAP-TEE-M", "edit_color_size", True),
        ("NL-JKT-BLU-M", "confirm_brand", True),
        ("NL-SNK-WHT-38", "view_only", True),
        ("NL-X05-NAV-M", "edit_color_size", True),
        ("NL-GAP-BELT-BRN", "view_only", True),
        ("TT-GHOST-001", "pick_feed_image", False),
        ("TT-GHOST-002", "view_only", False),
    ],
)
def test_each_tiktok_issue_expectation(offer_id, expected_action, should_match):
    from adfeed.mock_catalog import catalog_stats, mock_tiktok_issues
    from adfeed.platforms.common.issue_actions import suggest_action
    from adfeed.platforms.common.offer_match import match_offer_to_sku

    issue = next(i for i in mock_tiktok_issues() if i["offer_id"] == offer_id)
    assert suggest_action(issue["reason_code"])["action"] == expected_action
    internal = match_offer_to_sku(offer_id, set(catalog_stats()["skus"]))
    assert (internal == offer_id) is should_match


def test_meta_xml_and_tiktok_csv_content_from_pipeline(mock_store, tmp_path):
    """Open generated Meta XML + TikTok CSV and spot-check required fields."""
    store_db, store, seeded = mock_store
    # Use a small apparel subset for fast, readable files
    handles = {"wide-leg-trousers", "midi-a-line-skirt", "classic-denim-jacket"}
    products = [p for p in store_db.get_store_products(store.id) if p.handle in handles]
    pids = [p.id for p in products]

    _, feeds = _optimize_and_generate(store_db, store, pids, ["meta", "tiktok"])
    by_plat = {u["platform"]: u for u in feeds["feed_urls"]}

    # Resolve local paths from store feed dir (URL may be public base)
    meta_path = Path(ROOT) / "feeds" / store.id / "meta" / "us.xml"
    # ADFEED_DATA_DIR may redirect feeds — also try url path basename via store_db configs
    if not meta_path.exists():
        # pipeline writes under phase0/feeds or ADFEED_DATA_DIR/feeds
        from adfeed import config

        data = Path(getattr(config, "DATA_DIR", ROOT))
        meta_path = data / "feeds" / store.id / "meta" / "us.xml"
    assert meta_path.exists(), f"missing meta feed at {meta_path}; feeds={feeds}"
    meta_xml = meta_path.read_text(encoding="utf-8")
    assert "<id>NL-PANT-BLK-M</id>" in meta_xml or "<id>NL-PANT-BLK-S</id>" in meta_xml
    assert "<brand>Northline</brand>" in meta_xml
    assert "eprolo" not in meta_xml.lower()

    tt_path = meta_path.parent.parent / "tiktok" / "us.csv"
    if not tt_path.exists():
        tt_path = Path(ROOT) / "feeds" / store.id / "tiktok" / "us.csv"
    assert tt_path.exists(), f"missing tiktok feed at {tt_path}"
    rows = list(csv.DictReader(io.StringIO(tt_path.read_text(encoding="utf-8"))))
    assert len(rows) >= 9
    assert all(r.get("Brand") == "Northline" or r.get("Brand") for r in rows)
    # Real catalog weights may pass through; invented package dims must stay empty
    assert all((r.get("Package Length (cm)") or "") == "" for r in rows)
    assert all((r.get("Package Width (cm)") or "") == "" for r in rows)
    assert all((r.get("Package Height (cm)") or "") == "" for r in rows)
