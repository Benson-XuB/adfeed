"""FastAPI routes for TikTok Shop connect + feed URL register."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from adfeed.shopify_auth import require_store
from adfeed.store_db import Store as StoreModel

router = APIRouter(tags=["tiktok"])


@router.get("/api/app/tiktok/status")
async def app_tiktok_status(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.tiktok.oauth import tiktok_oauth_configured

    tok = store_db.get_tiktok_oauth_token(store.id)
    return {
        "oauth_configured": tiktok_oauth_configured(),
        "connected": bool(tok),
        "scopes": (tok or {}).get("scopes") or "",
        "shops": store_db.list_tiktok_shops(store.id),
        "selected_shop_id": store_db.get_selected_tiktok_shop_id(store.id),
    }


@router.get("/api/app/tiktok/oauth/start")
async def app_tiktok_oauth_start(store: StoreModel = Depends(require_store)):
    from adfeed.platforms.tiktok.oauth import (
        build_authorize_url,
        make_oauth_state,
        tiktok_oauth_configured,
    )

    if not tiktok_oauth_configured():
        raise HTTPException(503, "TikTok OAuth is not configured (TIKTOK_*).")
    state = make_oauth_state(store.id)
    try:
        url = build_authorize_url(state=state)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {"authorize_url": url, "state": state}


@router.get("/api/app/tiktok/oauth/callback")
async def app_tiktok_oauth_callback(code: str = "", state: str = "", error: str = ""):
    from adfeed import store_db
    from adfeed.platforms.tiktok.oauth import (
        exchange_authorization_code,
        parse_oauth_state,
        seal_token,
    )
    from adfeed.platforms.tiktok.shop_client import HttpTikTokShopClient

    if error:
        return HTMLResponse(
            f"<html><body><p>TikTok authorization failed: {error}</p>"
            "<p>You can close this window.</p></body></html>",
            status_code=400,
        )
    if not code or not state:
        raise HTTPException(400, "Missing code or state")
    try:
        parsed = parse_oauth_state(state)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    store_id = parsed["store_id"]
    if not store_db.get_store(store_id):
        raise HTTPException(404, "Store not found")
    try:
        tokens = exchange_authorization_code(code)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e
    store_db.upsert_tiktok_oauth_token(
        store_id,
        seal_token(tokens["refresh_token"]),
        seal_token(tokens["access_token"]),
        tokens.get("scopes") or "",
    )
    try:
        for s in HttpTikTokShopClient(tokens["access_token"]).list_shops():
            store_db.upsert_tiktok_shop(
                store_id,
                s["shop_id"],
                s.get("display_name") or "",
                cipher=s.get("cipher") or "",
                select=False,
            )
        shops = store_db.list_tiktok_shops(store_id)
        if len(shops) == 1:
            store_db.upsert_tiktok_shop(
                store_id,
                shops[0]["shop_id"],
                shops[0].get("display_name") or "",
                cipher=shops[0].get("cipher") or "",
                select=True,
            )
    except Exception:
        pass
    return HTMLResponse(
        "<html><body><p>TikTok connected. You can close this window and return to AdFeed.</p>"
        "<script>try{window.close()}catch(e){}</script></body></html>"
    )


class TikTokShopSelectBody(BaseModel):
    shop_id: str
    display_name: str = ""


@router.post("/api/app/tiktok/shops/select")
async def app_tiktok_shop_select(
    body: TikTokShopSelectBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db

    if not store_db.get_tiktok_oauth_token(store.id):
        raise HTTPException(400, "Connect TikTok first")
    row = store_db.upsert_tiktok_shop(
        store.id, body.shop_id, body.display_name, select=True
    )
    return {"ok": True, "shop": row}


@router.post("/api/app/tiktok/shops/refresh")
async def app_tiktok_shops_refresh(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.tiktok.oauth import access_token_for_store
    from adfeed.platforms.tiktok.shop_client import HttpTikTokShopClient

    if not store_db.get_tiktok_oauth_token(store.id):
        raise HTTPException(400, "Connect TikTok first")
    try:
        shops = HttpTikTokShopClient(access_token_for_store(store.id)).list_shops()
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    for s in shops:
        store_db.upsert_tiktok_shop(
            store.id,
            s["shop_id"],
            s.get("display_name") or "",
            cipher=s.get("cipher") or "",
            select=False,
        )
    return {"ok": True, "shops": store_db.list_tiktok_shops(store.id)}


@router.post("/api/app/tiktok/disconnect")
async def app_tiktok_disconnect(store: StoreModel = Depends(require_store)):
    from adfeed import store_db

    store_db.delete_tiktok_oauth_token(store.id)
    return {"ok": True}


class TikTokAttachBody(BaseModel):
    shop_id: Optional[str] = None
    country: str = "US"
    mock_result: Optional[dict] = None


@router.post("/api/app/tiktok/feed/attach")
async def app_tiktok_feed_attach(
    body: TikTokAttachBody,
    store: StoreModel = Depends(require_store),
):
    """Register this store's TikTok CSV feed URL against the selected shop."""
    from adfeed import store_db
    from adfeed.config import PUBLIC_BASE_URL
    from adfeed.platforms.common.paths import durable_feed_url
    from adfeed.platforms.tiktok.shop_client import HttpTikTokShopClient

    sid = (body.shop_id or "").strip() or store_db.get_selected_tiktok_shop_id(store.id)
    if not sid:
        raise HTTPException(400, "Select a TikTok shop first")
    if not store_db.get_tiktok_oauth_token(store.id) and body.mock_result is None:
        raise HTTPException(400, "Connect TikTok first")

    country = (body.country or "US").upper()
    feed = store_db.get_store_feed(store.id, country, "tiktok")
    feed_url = (feed.feed_url if feed else "") or durable_feed_url(
        PUBLIC_BASE_URL, store.id, "tiktok", country
    )
    if body.mock_result is not None:
        result = dict(body.mock_result)
        result.setdefault("shop_id", sid)
        result.setdefault("feed_url", feed_url)
        result.setdefault("mode", "register")
    else:
        result = HttpTikTokShopClient("unused").register_feed_url(sid, feed_url)

    store_db.upsert_tiktok_shop(
        store.id,
        sid,
        select=True,
        feed_url=str(result.get("feed_url") or feed_url),
    )
    return {"ok": True, **result}
