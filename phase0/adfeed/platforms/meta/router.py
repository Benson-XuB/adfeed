"""FastAPI routes for Meta Catalog connect + feed attach."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from adfeed.shopify_auth import require_store
from adfeed.store_db import Store as StoreModel

router = APIRouter(tags=["meta"])


@router.get("/api/app/meta/status")
async def app_meta_status(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.meta.oauth import meta_oauth_configured

    tok = store_db.get_meta_oauth_token(store.id)
    return {
        "oauth_configured": meta_oauth_configured(),
        "connected": bool(tok),
        "scopes": (tok or {}).get("scopes") or "",
        "catalogs": store_db.list_meta_catalogs(store.id),
        "selected_catalog_id": store_db.get_selected_meta_catalog_id(store.id),
    }


@router.get("/api/app/meta/oauth/start")
async def app_meta_oauth_start(store: StoreModel = Depends(require_store)):
    from adfeed.platforms.meta.oauth import (
        build_authorize_url,
        make_oauth_state,
        meta_oauth_configured,
    )

    if not meta_oauth_configured():
        raise HTTPException(503, "Meta OAuth is not configured (META_*).")
    state = make_oauth_state(store.id)
    try:
        url = build_authorize_url(state=state)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {"authorize_url": url, "state": state}


@router.get("/api/app/meta/oauth/callback")
async def app_meta_oauth_callback(code: str = "", state: str = "", error: str = ""):
    from adfeed import store_db
    from adfeed.platforms.meta.catalog_client import HttpMetaCatalogClient
    from adfeed.platforms.meta.oauth import (
        exchange_authorization_code,
        parse_oauth_state,
        seal_access_token,
    )

    if error:
        return HTMLResponse(
            f"<html><body><p>Meta authorization failed: {error}</p>"
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
    store_db.upsert_meta_oauth_token(
        store_id,
        seal_access_token(tokens["access_token"]),
        tokens.get("scopes") or "",
    )
    try:
        for c in HttpMetaCatalogClient(tokens["access_token"]).list_catalogs():
            store_db.upsert_meta_catalog(
                store_id, c["catalog_id"], c.get("display_name") or "", select=False
            )
        cats = store_db.list_meta_catalogs(store_id)
        if len(cats) == 1:
            store_db.upsert_meta_catalog(
                store_id,
                cats[0]["catalog_id"],
                cats[0].get("display_name") or "",
                select=True,
            )
    except Exception:
        pass
    return HTMLResponse(
        "<html><body><p>Meta connected. You can close this window and return to AdFeed.</p>"
        "<script>try{window.close()}catch(e){}</script></body></html>"
    )


class MetaCatalogSelectBody(BaseModel):
    catalog_id: str
    display_name: str = ""


@router.post("/api/app/meta/catalogs/select")
async def app_meta_catalog_select(
    body: MetaCatalogSelectBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db

    if not store_db.get_meta_oauth_token(store.id):
        raise HTTPException(400, "Connect Meta first")
    row = store_db.upsert_meta_catalog(
        store.id, body.catalog_id, body.display_name, select=True
    )
    return {"ok": True, "catalog": row}


@router.post("/api/app/meta/catalogs/refresh")
async def app_meta_catalogs_refresh(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.meta.catalog_client import HttpMetaCatalogClient
    from adfeed.platforms.meta.oauth import access_token_for_store

    if not store_db.get_meta_oauth_token(store.id):
        raise HTTPException(400, "Connect Meta first")
    try:
        client = HttpMetaCatalogClient(access_token_for_store(store.id))
        catalogs = client.list_catalogs()
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    for c in catalogs:
        store_db.upsert_meta_catalog(
            store.id, c["catalog_id"], c.get("display_name") or "", select=False
        )
    return {"ok": True, "catalogs": store_db.list_meta_catalogs(store.id)}


@router.post("/api/app/meta/disconnect")
async def app_meta_disconnect(store: StoreModel = Depends(require_store)):
    from adfeed import store_db

    store_db.delete_meta_oauth_token(store.id)
    return {"ok": True}


class MetaAttachBody(BaseModel):
    catalog_id: Optional[str] = None
    country: str = "US"
    mock_result: Optional[dict] = None


@router.post("/api/app/meta/feed/attach")
async def app_meta_feed_attach(
    body: MetaAttachBody,
    store: StoreModel = Depends(require_store),
):
    """Attach this store's Meta feed URL to the selected catalog (scheduled fetch)."""
    from adfeed import store_db
    from adfeed.config import PUBLIC_BASE_URL
    from adfeed.platforms.common.paths import durable_feed_url
    from adfeed.platforms.meta.catalog_client import HttpMetaCatalogClient
    from adfeed.platforms.meta.oauth import access_token_for_store

    cid = (body.catalog_id or "").strip() or store_db.get_selected_meta_catalog_id(store.id)
    if not cid:
        raise HTTPException(400, "Select a Meta catalog first")
    if not store_db.get_meta_oauth_token(store.id) and body.mock_result is None:
        raise HTTPException(400, "Connect Meta first")

    country = (body.country or "US").upper()
    feed = store_db.get_store_feed(store.id, country, "meta")
    feed_url = (feed.feed_url if feed else "") or durable_feed_url(
        PUBLIC_BASE_URL, store.id, "meta", country
    )
    if body.mock_result is not None:
        result = dict(body.mock_result)
        result.setdefault("product_feed_id", "mock-feed")
        result.setdefault("catalog_id", cid)
        result.setdefault("feed_url", feed_url)
    else:
        try:
            client = HttpMetaCatalogClient(access_token_for_store(store.id))
            result = client.attach_scheduled_feed(cid, feed_url=feed_url)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e

    store_db.upsert_meta_catalog(
        store.id,
        cid,
        select=True,
        product_feed_id=str(result.get("product_feed_id") or ""),
    )
    return {"ok": True, **result}
