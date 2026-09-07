"""FastAPI routes: /api/app/google/* for MC Push."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from adfeed import store_db
from adfeed.google_mc_push import datasources as ds
from adfeed.google_mc_push import oauth as goauth
from adfeed.google_mc_push import push as pushmod
from adfeed.google_mc_push.accounts import list_merchant_accounts
from adfeed.shopify_auth import require_store
from adfeed.store_db import Store as StoreModel

router = APIRouter(prefix="/api/app/google", tags=["app-google-mc-push"])


class MerchantBody(BaseModel):
    merchant_id: str = Field(..., min_length=1, max_length=64)


class PushBody(BaseModel):
    feed_file_id: Optional[str] = None
    country: Optional[str] = None
    content_language: str = "en"
    feed_label: Optional[str] = None


@router.get("/status")
async def google_status(store: StoreModel = Depends(require_store)):
    conn = store_db.get_google_connection(store.id) or {}
    return {
        "configured": goauth.google_oauth_configured(),
        "connected": bool(conn.get("refresh_token") or conn.get("access_token")),
        "merchant_id": conn.get("merchant_id") or "",
        "data_source_id": conn.get("data_source_id") or "",
        "data_source_name": conn.get("data_source_name") or "",
        "latest_push": store_db.latest_google_push_run(store.id),
    }


@router.get("/oauth/start")
async def google_oauth_start(store: StoreModel = Depends(require_store)):
    if not goauth.google_oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        url = goauth.build_authorize_url(store_id=store.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"authorize_url": url}


@router.get("/oauth/callback")
async def google_oauth_callback(
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    """Browser returns here without Shopify session — store_id is in state JWT."""
    store_id = goauth.verify_state(state or "")
    store = store_db.get_store(store_id) if store_id else None
    dest_shop = (store.shopify_domain if store else "") or ""
    fail_q = "google_error=1"

    if error or not code or not store:
        return RedirectResponse(
            f"https://{dest_shop}/admin" if dest_shop else "https://deltfu.com/?google_error=1",
            status_code=302,
        )

    try:
        tokens = goauth.exchange_code(code)
        store_db.upsert_google_connection(
            store.id,
            refresh_token=tokens.get("refresh_token") or "",
            access_token=tokens.get("access_token") or "",
            token_expiry=goauth.expiry_iso_from_expires_in(tokens.get("expires_in")),
        )
    except Exception:
        return RedirectResponse(
            f"https://{dest_shop}/admin?google_error=token",
            status_code=302,
        )

    # Prefer deep link into app; client_id may be empty in local — still OK.
    app_handle = os.getenv("SHOPIFY_APP_HANDLE") or os.getenv("SHOPIFY_CLIENT_ID") or ""
    if app_handle and dest_shop:
        return RedirectResponse(
            f"https://{dest_shop}/admin/apps/{app_handle}?google_connected=1",
            status_code=302,
        )
    return RedirectResponse(
        f"https://{dest_shop}/admin?google_connected=1" if dest_shop else "https://deltfu.com/",
        status_code=302,
    )


@router.post("/logout")
async def google_logout(store: StoreModel = Depends(require_store)):
    store_db.clear_google_connection(store.id)
    return {"ok": True}


@router.get("/accounts")
async def google_accounts(store: StoreModel = Depends(require_store)):
    conn = store_db.get_google_connection(store.id)
    if not conn:
        raise HTTPException(status_code=401, detail="Connect Google first")
    try:
        access, patch = goauth.ensure_store_access_token(conn)
        if patch:
            store_db.upsert_google_connection(store.id, **patch)
        accounts = list_merchant_accounts(access)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"ok": True, "accounts": accounts}


@router.post("/merchant")
async def select_merchant(body: MerchantBody, store: StoreModel = Depends(require_store)):
    mid = body.merchant_id.strip()
    if not mid.isdigit():
        raise HTTPException(status_code=400, detail="merchant_id must be numeric")
    conn = store_db.get_google_connection(store.id)
    if not conn:
        raise HTTPException(status_code=401, detail="Connect Google first")
    try:
        access, patch = goauth.ensure_store_access_token(conn)
        if patch:
            store_db.upsert_google_connection(store.id, **patch)
        ensured = ds.ensure_adfeed_data_source(access, mid)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    store_db.upsert_google_connection(
        store.id,
        merchant_id=mid,
        data_source_id=ensured["data_source_id"],
        data_source_name=ensured.get("data_source_name") or "AdFeed",
    )
    return {
        "ok": True,
        "merchant_id": mid,
        "data_source_id": ensured["data_source_id"],
        "data_source_name": ensured.get("data_source_name") or "AdFeed",
    }


def _resolve_feed_file(store: StoreModel, body: PushBody):
    if body.feed_file_id:
        feed = store_db.get_feed_file(body.feed_file_id)
        if not feed or feed.store_id != store.id:
            raise HTTPException(status_code=404, detail="feed_file_id not found")
        return feed
    country = (body.country or "").strip().upper()
    feeds = [
        f
        for f in store_db.list_store_feeds(store.id)
        if (f.platform or "google").lower() == "google"
        and (not country or (f.country or "").upper() == country)
    ]
    if not feeds:
        raise HTTPException(status_code=400, detail="Generate a Google feed first")
    feeds.sort(key=lambda x: x.updated_at or x.generated_at or x.created_at or "", reverse=True)
    return feeds[0]


@router.post("/push")
async def google_push(body: PushBody, store: StoreModel = Depends(require_store)):
    conn = store_db.get_google_connection(store.id)
    if not conn or not (conn.get("refresh_token") or conn.get("access_token")):
        raise HTTPException(status_code=401, detail="Connect Google first")
    merchant_id = (conn.get("merchant_id") or "").strip()
    if not merchant_id:
        raise HTTPException(status_code=400, detail="Select a Merchant account first")

    feed = _resolve_feed_file(store, body)
    path = Path(feed.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Feed file missing on disk")

    feed_label = (body.feed_label or feed.country or "US").upper()
    content_language = body.content_language or "en"

    try:
        access, patch = goauth.ensure_store_access_token(conn)
        if patch:
            store_db.upsert_google_connection(store.id, **patch)
            conn = store_db.get_google_connection(store.id) or conn

        data_source_id = (conn.get("data_source_id") or "").strip()
        if not data_source_id:
            ensured = ds.ensure_adfeed_data_source(
                access,
                merchant_id,
                content_language=content_language,
                feed_label=feed_label,
                country=feed_label,
            )
            store_db.upsert_google_connection(
                store.id,
                data_source_id=ensured["data_source_id"],
                data_source_name=ensured.get("data_source_name") or "AdFeed",
            )
            data_source_id = ensured["data_source_id"]

        excluded = store_db.get_feed_excluded_skus(
            store.id, feed.country or feed_label, feed.platform or "google"
        )
        rows = pushmod.load_pushable_rows(path, excluded_skus=set(excluded))
        if not rows:
            raise HTTPException(status_code=400, detail="No SKUs to push (empty or all excluded)")

        result = pushmod.push_rows(
            access,
            merchant_id,
            data_source_id,
            rows,
            content_language=content_language,
            feed_label=feed_label,
        )
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    run_id = store_db.save_google_push_run(
        store.id,
        merchant_id=merchant_id,
        data_source_id=data_source_id,
        status="completed",
        success_count=result["success_count"],
        failure_count=result["failure_count"],
        failures=result.get("failures") or [],
    )
    result["run_id"] = run_id
    result["feed_file_id"] = feed.id
    result["item_attempted"] = len(rows)
    return result
