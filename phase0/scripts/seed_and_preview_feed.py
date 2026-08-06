#!/usr/bin/env python3
"""Seed a stores row from .env and optionally sync + generate Google-US feed.

Usage:
  cd phase0
  python scripts/seed_and_preview_feed.py              # seed store only
  python scripts/seed_and_preview_feed.py --limit 3    # sync 3 products + generate
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Sync N products and generate Google-US feed")
    parser.add_argument("--platforms", default="google", help="Comma list: google,meta,tiktok")
    parser.add_argument("--languages", default="US", help="Comma list: US,DE,...")
    args = parser.parse_args()

    shop = os.getenv("SHOPIFY_STORE") or os.getenv("SHOPIFY_SHOP_DOMAIN") or ""
    token = os.getenv("SHOPIFY_ACCESS_TOKEN") or ""
    if not shop or not token:
        print("ERROR: set SHOPIFY_STORE and SHOPIFY_ACCESS_TOKEN in phase0/.env")
        sys.exit(1)
    if not shop.endswith(".myshopify.com"):
        shop = f"{shop.replace('.myshopify.com', '')}.myshopify.com"

    from adfeed.db import init_db, get_user_by_email, create_user
    init_db()
    from adfeed import store_db
    store_db.init_store_schema()

    user = get_user_by_email("shopify-app@adfeed.ai") or create_user(
        email="shopify-app@adfeed.ai", name="Shopify App",
    )
    store = store_db.get_store_by_domain(shop)
    if store:
        store_db.update_store(
            store.id,
            access_token=token,
            status="active",
            quota_total=max(store.quota_total, 500),
        )
        store = store_db.get_store(store.id)
    else:
        store = store_db.create_store(
            user_id=user.id,
            shopify_domain=shop,
            shop_name=shop.replace(".myshopify.com", ""),
            access_token=token,
            quota_total=500,
        )

    print(f"Store ready: {store.id}")
    print(f"  domain={store.shopify_domain}")
    print(f"  has_token={bool(store.access_token)}")
    print(f"  quota={store.quota_used}/{store.quota_total}")

    if args.limit <= 0:
        print("Done (seed only). Re-run with --limit 3 to generate a preview feed.")
        return

    from adfeed.shopify_client import fetch_shopify_products
    from adfeed.store_sync import upsert_raw_shopify_product, normalize_shopify_product_id
    import httpx
    from adfeed.config import SHOPIFY_API_VERSION

    data = await fetch_shopify_products(shop, token, limit=min(args.limit, 50))
    # fetch_shopify_products returns mapped products; we need raw for variants — re-fetch by id
    ids = [normalize_shopify_product_id(p.get("shopify_id")) for p in data.get("products", [])][: args.limit]
    print(f"Syncing {len(ids)} products...")

    internal = []
    shop_short = shop.replace(".myshopify.com", "")
    async with httpx.AsyncClient(timeout=30) as client:
        for pid in ids:
            resp = await client.get(
                f"https://{shop_short}.myshopify.com/admin/api/{SHOPIFY_API_VERSION}/products/{pid}.json",
                headers={"X-Shopify-Access-Token": token},
            )
            if resp.status_code != 200:
                print(f"  skip {pid}: HTTP {resp.status_code}")
                continue
            raw = resp.json().get("product")
            saved = upsert_raw_shopify_product(store.id, raw)
            internal.append(saved.id)
            print(f"  synced {pid}: {saved.title[:60]}")

    if not internal:
        print("No products synced.")
        return

    platforms = [p.strip().lower() for p in args.platforms.split(",") if p.strip()]
    languages = [l.strip().upper() for l in args.languages.split(",") if l.strip()]

    from adfeed.pipeline import optimize_layered, generate_feed_for_store
    print(f"Running optimize_layered ({len(internal)} SKU × {platforms} × {languages})...")
    opt = optimize_layered(
        store_id=store.id,
        product_ids=internal,
        platforms=platforms,
        languages=languages,
        remove_watermarks=False,
    )
    print(f"  ok={opt['ok_units']} fail={opt['fail_units']} assets={opt['assets_written']}")

    feeds = generate_feed_for_store(
        store_id=store.id,
        countries=languages,
        platforms=platforms,
    )
    print("Feeds:")
    for f in feeds.get("feed_urls", []):
        print(f"  [{f.get('platform')}/{f.get('country')}] {f.get('url')} ({f.get('items')} items)")

    # Print sample titles from assets
    from adfeed.store_db import get_product_asset_by_key, get_product
    print("\nSample titles:")
    for pid in internal[:3]:
        p = get_product(pid)
        for plat in platforms:
            for lang in languages:
                a = get_product_asset_by_key(pid, plat, lang)
                if a:
                    print(f"  {p.title[:40]} → [{plat}/{lang}] {a.title[:80]}")


if __name__ == "__main__":
    asyncio.run(main())
