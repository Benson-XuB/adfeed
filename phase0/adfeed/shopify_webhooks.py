"""Shopify webhook HMAC verification + catalog/uninstall/GDPR handlers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Optional

from . import config
from . import store_db

logger = logging.getLogger("adfeed-webhooks")


def verify_shopify_hmac(raw_body: bytes, hmac_header: str) -> bool:
    """Verify X-Shopify-Hmac-Sha256 against app client secret."""
    secret = config.SHOPIFY_CLIENT_SECRET or os.getenv("SHOPIFY_API_SECRET", "")
    if not secret:
        # No secret configured — treat as skip (dev); production must set secret
        return os.getenv("ADFEED_WEBHOOK_SKIP_HMAC", "").lower() in ("1", "true", "yes")
    if not hmac_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode("utf-8")
    return hmac.compare_digest(computed, hmac_header)


def handle_products_update(shop_domain: str, payload: dict) -> dict:
    """Refresh or upsert product snapshot from products/update webhook."""
    shop = _norm_shop(shop_domain)
    store = store_db.get_store_by_domain(shop) if shop else None
    if not store:
        return {"ok": False, "reason": "store_not_found"}

    pid = str(payload.get("id") or "")
    title = payload.get("title") or ""
    status = (payload.get("status") or "active").lower()
    handle = payload.get("handle")
    vendor = payload.get("vendor")
    product_type = payload.get("product_type")
    images = payload.get("images") or []
    image_url = images[0].get("src") if images else None
    body_html = payload.get("body_html") or ""

    if not pid:
        return {"ok": False, "reason": "missing_product_id"}

    # Soft-disable drafts/archived
    db_status = "active" if status == "active" else "disabled"

    existing = None
    products = store_db.get_store_products(store.id, status="active")
    products += store_db.get_store_products(store.id, status="disabled")
    for p in products:
        if p.shopify_product_id == pid or p.id == pid:
            existing = p
            break

    if existing:
        store_db.update_product(
            existing.id,
            title=title or existing.title,
            handle=handle,
            vendor=vendor,
            product_type=product_type,
            image_url=image_url or existing.image_url,
            description=body_html or existing.description,
            status=db_status,
        )
        return {"ok": True, "action": "updated", "product_id": existing.id}

    created = store_db.save_product(
        store.id,
        title=title or "Untitled",
        shopify_product_id=pid,
        handle=handle,
        vendor=vendor,
        product_type=product_type,
        image_url=image_url,
        description=body_html,
        status=db_status,
        ai_status="raw",
    )
    return {"ok": True, "action": "created", "product_id": created.id}


def handle_products_delete(shop_domain: str, payload: dict) -> dict:
    shop = _norm_shop(shop_domain)
    store = store_db.get_store_by_domain(shop) if shop else None
    if not store:
        return {"ok": False, "reason": "store_not_found"}
    pid = str(payload.get("id") or "")
    for p in store_db.get_store_products(store.id):
        if p.shopify_product_id == pid:
            store_db.update_product(p.id, status="disabled", feed_enabled=0)
            return {"ok": True, "action": "soft_deleted", "product_id": p.id}
    return {"ok": True, "action": "noop"}


def handle_app_uninstalled(shop_domain: str) -> dict:
    shop = _norm_shop(shop_domain)
    store = store_db.get_store_by_domain(shop) if shop else None
    if not store:
        return {"ok": False, "reason": "store_not_found"}
    store_db.update_store(
        store.id,
        access_token=None,
        status="inactive",
        billing_status="cancelled",
    )
    return {"ok": True, "store_id": store.id}


def handle_gdpr_stub(topic: str, payload: dict) -> dict:
    """Return 200-ready ack; persistence TODO for App Store review if required."""
    logger.info("GDPR webhook %s received (stub ack): keys=%s", topic, list(payload.keys()))
    return {"ok": True, "topic": topic, "todo": "persist_if_required_for_review"}


def _norm_shop(shop_domain: str) -> str:
    raw = (shop_domain or "").strip().lower().replace("https://", "").replace("http://", "")
    if raw and not raw.endswith(".myshopify.com"):
        raw = f"{raw}.myshopify.com"
    return raw
