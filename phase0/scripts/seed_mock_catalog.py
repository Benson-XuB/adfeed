#!/usr/bin/env python3
"""Seed a local-only mock store (no live Shopify). Safe during App Store review.

Usage:
  cd phase0
  .venv/bin/python scripts/seed_mock_catalog.py
  .venv/bin/python scripts/seed_mock_catalog.py --generate
  .venv/bin/python scripts/seed_mock_catalog.py --issues-sync
  .venv/bin/python scripts/seed_mock_catalog.py --generate --issues-sync --export
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

EXPORT_DIR = ROOT / "feeds" / "mock-catalog"


def _optimize_side_effect(
    *,
    original_title,
    countries,
    description="",
    **kwargs,
):
    return {
        "optimized_titles": {lang: original_title for lang in countries},
        "description_snippets": {
            lang: (description or original_title)[:180] for lang in countries
        },
        "ai_tags_by_lang": {lang: [] for lang in countries},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed high-quality mock catalog (no Shopify)")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Optimize + generate Google XML + Meta XML + TikTok CSV",
    )
    parser.add_argument(
        "--issues-sync",
        action="store_true",
        help="Sync mock Google / Meta / TikTok issues",
    )
    parser.add_argument(
        "--gmc-sync",
        action="store_true",
        help=argparse.SUPPRESS,  # alias kept for older docs
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help=f"Copy generated feeds into {EXPORT_DIR}",
    )
    parser.add_argument(
        "--platforms",
        default="google,meta,tiktok",
        help="Comma list for --generate (default: google,meta,tiktok)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Only use first N products for --generate (0 = all)",
    )
    args = parser.parse_args()
    if args.gmc_sync:
        args.issues_sync = True

    from adfeed.db import init_db, create_user, get_user_by_email
    from adfeed import store_db
    from adfeed.mock_catalog import (
        MOCK_MERCHANT_ID,
        MOCK_META_CATALOG_ID,
        MOCK_SHOP_DOMAIN,
        MOCK_TIKTOK_SHOP_ID,
        ensure_mock_store,
        mock_gmc_issues,
        mock_meta_issues,
        mock_tiktok_issues,
    )

    init_db()
    store_db.init_store_schema()
    store, seeded = ensure_mock_store(
        store_db, create_user=create_user, get_user_by_email=get_user_by_email
    )

    stats = seeded["stats"]
    print(f"Mock store ready: {store.id}")
    print(f"  domain={store.shopify_domain} (NOT your live shop)")
    print(f"  brand={store.default_brand}")
    print(f"  products={stats['products']} variants={stats['variants']}")
    print(f"  types={', '.join(stats['product_types'])}")
    assert store.shopify_domain == MOCK_SHOP_DOMAIN

    product_ids = seeded["product_ids"]
    if args.limit and args.limit > 0:
        product_ids = product_ids[: args.limit]

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]

    if args.generate:
        from adfeed.pipeline import optimize_layered, generate_feed_for_store

        print(f"Optimizing {len(product_ids)} products × {platforms} (LLM mocked)...")
        with patch("adfeed.pipeline.load_gpc_taxonomy"), patch(
            "adfeed.pipeline.gpc_match",
            return_value={
                "gpc_code": "2271",
                "gpc_path": "Apparel & Accessories > Clothing",
                "confidence": 0.9,
                "source": "mock",
            },
        ), patch(
            "adfeed.pipeline.optimize_multi_country",
            side_effect=_optimize_side_effect,
        ), patch(
            "adfeed.pipeline.infer_product_attributes",
            return_value={},
        ):
            opt = optimize_layered(
                store_id=store.id,
                product_ids=product_ids,
                platforms=platforms,
                languages=["US"],
            )
        print(f"  optimize: ok_units={opt.get('ok_units')} assets={opt.get('assets_written')}")

        feeds = generate_feed_for_store(
            store.id,
            countries=["US"],
            platforms=platforms,
            product_ids=product_ids,
        )
        print(f"  feeds: {feeds.get('feed_urls')}")
        print(f"  total_items={feeds.get('total_items')}")

        for handle in ("wide-leg-trousers", "midi-a-line-skirt", "classic-denim-jacket"):
            prods = [p for p in store_db.get_store_products(store.id) if p.handle == handle]
            if not prods:
                continue
            for plat in platforms:
                asset = store_db.get_product_asset_by_key(prods[0].id, plat, "US")
                title = (asset.title if asset else None) or prods[0].title
                print(f"  check {handle}/{plat}: title={title!r}")

        if args.export:
            _export_feeds(store.id, platforms)

    if args.issues_sync:
        from adfeed.platforms.google.merchant_sync import sync_merchant_issues
        from adfeed.platforms.meta.issues_sync import sync_meta_issues
        from adfeed.platforms.tiktok.issues_sync import sync_tiktok_issues
        from adfeed.platforms.common.issue_actions import suggest_action

        class _G:
            def list_product_issues(self, merchant_id: str):
                return mock_gmc_issues()

        class _M:
            def list_product_issues(self, catalog_id: str):
                return mock_meta_issues()

        class _T:
            def list_product_issues(self, shop_id: str):
                return mock_tiktok_issues()

        store_db.upsert_google_merchant_account(store.id, MOCK_MERCHANT_ID, select=True)
        g = sync_merchant_issues(store.id, MOCK_MERCHANT_ID, _G())
        m = sync_meta_issues(store.id, MOCK_META_CATALOG_ID, _M())
        t = sync_tiktok_issues(store.id, MOCK_TIKTOK_SHOP_ID, _T())
        print(
            f"Issues sync — google written={g['written']} matched={g['matched']} unmatched={g['unmatched']}"
        )
        print(
            f"Issues sync — meta   written={m['written']} matched={m['matched']} unmatched={m['unmatched']}"
        )
        print(
            f"Issues sync — tiktok written={t['written']} matched={t['matched']} unmatched={t['unmatched']}"
        )
        for label, rows in (
            ("google", store_db.list_gmc_product_issues(store.id, MOCK_MERCHANT_ID)),
            ("meta", store_db.list_meta_product_issues(store.id, MOCK_META_CATALOG_ID)),
            ("tiktok", store_db.list_tiktok_product_issues(store.id, MOCK_TIKTOK_SHOP_ID)),
        ):
            print(f"  -- {label} --")
            for r in rows[:8]:
                action = suggest_action(r.get("reason_code") or "")["action"]
                print(
                    f"  {r['offer_id']}: {r['status']} {r['reason_code']} → {action} "
                    f"matched={bool(r['product_id_internal'])}"
                )
            if len(rows) > 8:
                print(f"  ... +{len(rows) - 8} more")

    if not args.generate and not args.issues_sync:
        print("Done (seed only). Re-run with --generate / --issues-sync / --export.")
    return 0


def _export_feeds(store_id: str, platforms: list[str]) -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    src_root = ROOT / "feeds" / store_id
    mapping = {
        "google": ("google/us.xml", "google-us.xml"),
        "meta": ("meta/us.xml", "meta-us.xml"),
        "tiktok": ("tiktok/us.csv", "tiktok-us.csv"),
    }
    for plat in platforms:
        if plat not in mapping:
            continue
        rel, dest_name = mapping[plat]
        src = src_root / rel
        if not src.exists():
            # some exporters may use uppercase
            alt = src_root / rel.replace("/us.", "/US.")
            src = alt if alt.exists() else src
        if not src.exists():
            print(f"  export skip missing {src}")
            continue
        dst = EXPORT_DIR / dest_name
        shutil.copy2(src, dst)
        print(f"  exported {dst} ({dst.stat().st_size} bytes)")


if __name__ == "__main__":
    raise SystemExit(main())
