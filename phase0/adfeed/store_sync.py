"""Shopify App store bootstrap + product sync into store_db."""

from __future__ import annotations

import logging
import re
from typing import Optional, Sequence

import httpx

from . import config
from . import store_db
from .config import SHOPIFY_CLIENT_ID, SHOPIFY_CLIENT_SECRET

logger = logging.getLogger("adfeed-store-sync")


def normalize_shopify_product_id(product_id: str) -> str:
    """GraphQL gid://shopify/Product/123 → '123'; also accepts plain numeric."""
    raw = str(product_id or "").strip()
    if not raw:
        return ""
    if "Product/" in raw:
        raw = raw.rsplit("Product/", 1)[-1]
    if "/" in raw:
        raw = raw.rsplit("/", 1)[-1]
    return raw


def normalize_shop_domain(shop: str) -> str:
    s = (shop or "").strip().lower().replace("https://", "").replace("http://", "")
    s = s.split("/")[0]
    if s and not s.endswith(".myshopify.com"):
        s = f"{s}.myshopify.com"
    return s


async def exchange_session_for_offline_token(
    shop_domain: str,
    session_token: str,
) -> Optional[dict]:
    """Exchange App Bridge session JWT for expiring offline Admin API token.

    Public apps must pass ``expiring=1`` — non-expiring offline tokens get
    HTTP 403 on Admin API ("Non-expiring access tokens are no longer accepted").
    """
    shop = normalize_shop_domain(shop_domain).replace(".myshopify.com", "")
    client_id = SHOPIFY_CLIENT_ID or config.SHOPIFY_CLIENT_ID
    client_secret = SHOPIFY_CLIENT_SECRET or config.SHOPIFY_CLIENT_SECRET
    if not client_id or not client_secret:
        logger.error("SHOPIFY_CLIENT_ID/SECRET missing for token exchange")
        return None

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": session_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:id_token",
        "requested_token_type": "urn:shopify:params:oauth:token-type:offline-access-token",
        # Required for Admin API on public apps (2026+).
        "expiring": "1",
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{shop}.myshopify.com/admin/oauth/access_token",
                data=data,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                logger.error(
                    "Token exchange failed: %s %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return None
            body = resp.json()
            token = body.get("access_token")
            if not token:
                return None
            return {
                "access_token": token,
                "scope": body.get("scope", ""),
                "expires_in": body.get("expires_in"),
                "refresh_token": body.get("refresh_token"),
                "refresh_token_expires_in": body.get("refresh_token_expires_in"),
            }
    except Exception as e:
        logger.error("Token exchange error: %s", e)
        return None


async def refresh_offline_access_token(
    shop_domain: str,
    refresh_token: str,
) -> Optional[dict]:
    """Refresh an expiring offline Admin API token (rotates refresh_token)."""
    shop = normalize_shop_domain(shop_domain).replace(".myshopify.com", "")
    client_id = SHOPIFY_CLIENT_ID or config.SHOPIFY_CLIENT_ID
    client_secret = SHOPIFY_CLIENT_SECRET or config.SHOPIFY_CLIENT_SECRET
    if not client_id or not client_secret or not refresh_token:
        return None
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://{shop}.myshopify.com/admin/oauth/access_token",
                data=data,
                headers={"Accept": "application/json"},
            )
            if resp.status_code != 200:
                logger.error(
                    "Token refresh failed: %s %s",
                    resp.status_code,
                    resp.text[:300],
                )
                return None
            body = resp.json()
            token = body.get("access_token")
            if not token:
                return None
            return {
                "access_token": token,
                "scope": body.get("scope", ""),
                "expires_in": body.get("expires_in"),
                "refresh_token": body.get("refresh_token") or refresh_token,
                "refresh_token_expires_in": body.get("refresh_token_expires_in"),
            }
    except Exception as e:
        logger.error("Token refresh error: %s", e)
        return None


def _persist_exchanged_token(store: store_db.Store, exchanged: dict) -> store_db.Store:
    """Write access_token (+ refresh metadata) and refresh shop profile fields."""
    from datetime import datetime, timedelta, timezone

    shop_name = store.shop_name
    site_url = store.site_url
    default_currency = store.default_currency
    try:
        from .shopify_admin_gql import fetch_shop

        info = fetch_shop(store.shopify_domain, exchanged["access_token"])
        shop_name = info.get("name") or shop_name
        domain = info.get("domain") or info.get("myshopify_domain")
        if domain and not str(domain).startswith("http"):
            site_url = f"https://{domain}"
        elif domain:
            site_url = str(domain)
        if info.get("currency"):
            default_currency = str(info["currency"]).strip().upper()
    except Exception as e:
        logger.warning("Shop info after exchange failed: %s", e)

    expires_in = exchanged.get("expires_in")
    expires_at = None
    if expires_in:
        try:
            expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=int(expires_in) - 60)
            ).isoformat()
        except (TypeError, ValueError):
            expires_at = None

    store_db.update_store(
        store.id,
        access_token=exchanged["access_token"],
        refresh_token=exchanged.get("refresh_token"),
        token_expires_at=expires_at,
        shop_name=shop_name,
        site_url=site_url,
        default_currency=default_currency,
        status="active",
    )
    return store_db.get_store(store.id) or store


async def ensure_store_access_token(
    store: store_db.Store,
    session_token: str,
    *,
    force: bool = False,
) -> store_db.Store:
    """Ensure store has a working expiring offline Admin API token.

    By default skips exchange if a token already works. Pass ``force=True``
    to re-exchange from the session JWT. Stale / non-expiring tokens cause
    GraphQL 403 and empty App product lists.
    """
    if store.access_token and not force:
        try:
            from .shopify_admin_gql import fetch_shop, graphql_payload

            # Probe with payload so we can detect non-expiring-token 403.
            probe = graphql_payload(
                store.shopify_domain,
                store.access_token,
                "{ shop { name myshopifyDomain } }",
            )
            err_text = str(probe.get("errors") or "") + str(probe.get("error_body") or "")
            if "Non-expiring access tokens" in err_text:
                logger.warning(
                    "Non-expiring offline token rejected for %s; re-exchanging",
                    store.shopify_domain,
                )
            else:
                info = (probe.get("data") or {}).get("shop") or {}
                # Also try fetch_shop shape used elsewhere
                if not info:
                    info = fetch_shop(store.shopify_domain, store.access_token) or {}
                if info.get("name") or info.get("myshopifyDomain") or info.get("myshopify_domain") or info.get("domain"):
                    return store
                # Token may be expired — try refresh_token before session exchange
                if getattr(store, "refresh_token", None):
                    refreshed = await refresh_offline_access_token(
                        store.shopify_domain, store.refresh_token,
                    )
                    if refreshed:
                        return _persist_exchanged_token(store, refreshed)
                logger.warning(
                    "Stored access_token appears stale for %s; re-exchanging",
                    store.shopify_domain,
                )
        except Exception as e:
            logger.warning(
                "Stored access_token invalid for %s (%s); re-exchanging",
                store.shopify_domain,
                e,
            )

    exchanged = await exchange_session_for_offline_token(
        store.shopify_domain, session_token,
    )
    if not exchanged:
        return store

    return _persist_exchanged_token(store, exchanged)


def refresh_store_currency_from_shopify(store: store_db.Store) -> store_db.Store:
    """Sync shop.json currency into stores.default_currency (sync helper for feed gen)."""
    if not store.access_token or not store.shopify_domain:
        return store
    try:
        from .shopify_admin_gql import fetch_shop
        info = fetch_shop(store.shopify_domain, store.access_token)
        currency = str(info.get("currency") or "").strip().upper()
        if not currency:
            return store
        if currency != (store.default_currency or "").upper():
            store_db.update_store(store.id, default_currency=currency)
            logger.info("Updated store %s default_currency → %s", store.id[:8], currency)
        return store_db.get_store(store.id) or store
    except Exception as e:
        logger.warning("refresh_store_currency failed: %s", e)
        return store


def _option_maps(product: dict) -> tuple[dict, dict]:
    """Return (position→name, name→position) for color/size extraction."""
    pos_to_name = {}
    name_to_pos = {}
    for opt in product.get("options") or []:
        pos = int(opt.get("position") or 0)
        name = (opt.get("name") or "").strip().lower()
        if pos:
            pos_to_name[pos] = name
            name_to_pos[name] = pos
    return pos_to_name, name_to_pos


def _variant_color_size(variant: dict, pos_to_name: dict) -> tuple[str, str]:
    color, size = "", ""
    for pos in (1, 2, 3):
        val = variant.get(f"option{pos}") or ""
        if not val or val.lower() in ("default title", "default"):
            continue
        name = pos_to_name.get(pos, "")
        if "color" in name or "colour" in name or "farbe" in name or "颜色" in name:
            color = val
        elif "size" in name or "größe" in name or "taille" in name or "尺码" in name:
            size = val
    if not color and not size:
        # fallback: option1=color, option2=size heuristic
        color = variant.get("option1") or ""
        size = variant.get("option2") or ""
        if color.lower() in ("default title", "default"):
            color = ""
    return color, size


def upsert_raw_shopify_product(store_id: str, product: dict) -> store_db.Product:
    """Persist one Shopify Admin REST product + variants into store_db."""
    sid = str(product.get("id", ""))
    images = product.get("images") or []
    image_url = images[0].get("src") if images else None
    additional = ",".join(img.get("src", "") for img in images[1:5] if img.get("src"))
    status = (product.get("status") or "active").lower()
    db_status = "active" if status == "active" else "disabled"

    saved = store_db.save_product(
        store_id,
        title=product.get("title") or "Untitled",
        shopify_product_id=sid,
        handle=product.get("handle"),
        vendor=product.get("vendor"),
        product_type=product.get("product_type"),
        brand=product.get("vendor"),
        image_url=image_url,
        additional_images=additional or None,
        description=_strip_html(product.get("body_html") or ""),
        status=db_status,
        ai_status="raw",
        feed_enabled=0,
    )
    # Only overwrite brand when merchant confirmed default_brand (field contract).
    # Never silent-inject eprolo / DEFAULT_STORE_BRAND.
    store = store_db.get_store(store_id)
    confirmed = (store.default_brand if store else None) or ""
    confirmed = confirmed.strip()
    if confirmed and (saved.brand or "").strip().lower() != confirmed.lower():
        store_db.update_product(saved.id, brand=confirmed)
        saved = store_db.get_product(saved.id)

    pos_to_name, _ = _option_maps(product)
    variants = product.get("variants") or []
    for v in variants:
        color, size = _variant_color_size(v, pos_to_name)
        sku = (v.get("sku") or "").strip() or f"{sid}-{v.get('id')}"
        img_id = v.get("image_id")
        v_image = image_url
        if img_id:
            for img in images:
                if img.get("id") == img_id:
                    v_image = img.get("src") or v_image
                    break
        store_db.save_variant(
            saved.id,
            sku=sku,
            shopify_variant_id=str(v.get("id", "")),
            title=v.get("title"),
            color=color or None,
            size=size or None,
            price=float(v.get("price") or 0),
            compare_at_price=float(v["compare_at_price"]) if v.get("compare_at_price") else None,
            inventory=int(v.get("inventory_quantity") or 0),
            image_url=v_image,
            barcode=v.get("barcode") or None,
            status="active",
        )
    return saved


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", "\n", html or "")
    text = text.replace("\xa0", " ").replace("&nbsp;", " ").strip()
    try:
        from .desc_formatter import format_product_description
        return format_product_description(text)
    except Exception:
        return re.sub(r"\s+", " ", text).strip()


async def fetch_raw_product(
    shop_domain: str,
    access_token: str,
    product_id: str,
) -> Optional[dict]:
    pid = normalize_shopify_product_id(product_id)
    if not pid:
        return None
    try:
        from .shopify_admin_gql import fetch_product
        return fetch_product(shop_domain, access_token, pid)
    except Exception as e:
        logger.error("Fetch product %s error: %s", pid, e)
        return None


async def sync_products_for_generate(
    store: store_db.Store,
    product_ids: Sequence[str],
) -> list[str]:
    """Fetch selected Shopify products into store_db. Returns internal product UUIDs."""
    if not store.access_token:
        raise RuntimeError(
            "Store has no access_token. Open the App so /api/app/bootstrap can exchange a session token."
        )

    internal_ids: list[str] = []
    seen = set()
    for raw_id in product_ids:
        pid = normalize_shopify_product_id(raw_id)
        if not pid or pid in seen:
            continue
        seen.add(pid)

        # Prefer existing row
        existing = None
        for p in store_db.get_store_products(store.id, status="active"):
            if p.shopify_product_id == pid:
                existing = p
                break
        if not existing:
            for p in store_db.get_store_products(store.id, status="disabled"):
                if p.shopify_product_id == pid:
                    existing = p
                    break

        raw = await fetch_raw_product(store.shopify_domain, store.access_token, pid)
        if raw:
            saved = upsert_raw_shopify_product(store.id, raw)
            internal_ids.append(saved.id)
        elif existing:
            internal_ids.append(existing.id)
        else:
            logger.warning("Product %s not found remotely or locally", pid)

    return internal_ids
