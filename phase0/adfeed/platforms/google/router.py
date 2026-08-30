"""FastAPI routes for Google Merchant / Ads read loop."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from adfeed.shopify_auth import require_store
from adfeed.store_db import Store as StoreModel

router = APIRouter(tags=["google"])


@router.get("/api/app/google/status")
async def app_google_status(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.google.ads_client import ads_api_configured
    from adfeed.platforms.google.oauth import (
        SCOPE_ADWORDS,
        SCOPE_CONTENT,
        google_oauth_configured,
    )

    tok = store_db.get_google_oauth_token(store.id)
    scopes = (tok or {}).get("scopes") or ""
    merchants = store_db.list_google_merchant_accounts(store.id)
    return {
        "oauth_configured": google_oauth_configured(),
        "ads_api_configured": ads_api_configured(),
        "connected": bool(tok),
        "scopes": scopes,
        "has_content_scope": SCOPE_CONTENT in scopes,
        "has_ads_scope": SCOPE_ADWORDS in scopes,
        "merchants": merchants,
        "selected_merchant_id": store_db.get_selected_merchant_id(store.id),
    }


@router.get("/api/app/google/oauth/start")
async def app_google_oauth_start(
    store: StoreModel = Depends(require_store),
    ads: bool = False,
):
    from adfeed.platforms.google.oauth import (
        build_authorize_url,
        google_oauth_configured,
        make_oauth_state,
    )

    if not google_oauth_configured():
        raise HTTPException(503, "Google OAuth is not configured (GOOGLE_OAUTH_*).")
    phase = "ads" if ads else "mc"
    state = make_oauth_state(store.id, phase=phase)
    try:
        url = build_authorize_url(state=state, include_ads=ads)
    except RuntimeError as e:
        raise HTTPException(503, str(e)) from e
    return {"authorize_url": url, "state": state}


@router.get("/api/app/google/oauth/callback")
async def app_google_oauth_callback(
    code: str = "",
    state: str = "",
    error: str = "",
):
    from adfeed import store_db
    from adfeed.platforms.google.merchant_client import HttpMerchantClient
    from adfeed.platforms.google.oauth import (
        exchange_authorization_code,
        open_refresh_token,
        parse_oauth_state,
        seal_refresh_token,
    )

    if error:
        return HTMLResponse(
            f"<html><body><p>Google authorization failed: {error}</p>"
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
    phase = parsed["phase"]
    if not store_db.get_store(store_id):
        raise HTTPException(404, "Store not found")
    try:
        tokens = exchange_authorization_code(code)
    except RuntimeError as e:
        raise HTTPException(400, str(e)) from e

    refresh = tokens.get("refresh_token") or ""
    if not refresh:
        existing = store_db.get_google_oauth_token(store_id)
        if existing:
            try:
                refresh = open_refresh_token(existing["refresh_token_enc"])
            except Exception:
                refresh = ""
    if not refresh:
        raise HTTPException(
            400,
            "No refresh_token from Google — revoke prior grant and reconnect with consent.",
        )
    scopes = tokens.get("scope") or ""
    if phase == "ads" and "adwords" not in scopes:
        prev = store_db.get_google_oauth_token(store_id)
        if prev and prev.get("scopes"):
            merged = set((prev["scopes"] or "").split()) | set(scopes.split())
            scopes = " ".join(sorted(merged))
    store_db.upsert_google_oauth_token(store_id, seal_refresh_token(refresh), scopes)

    try:
        client = HttpMerchantClient(tokens["access_token"])
        for m in client.list_merchants():
            store_db.upsert_google_merchant_account(
                store_id,
                m["merchant_id"],
                m.get("display_name") or "",
                select=False,
            )
        merchants = store_db.list_google_merchant_accounts(store_id)
        if len(merchants) == 1:
            store_db.upsert_google_merchant_account(
                store_id,
                merchants[0]["merchant_id"],
                merchants[0].get("display_name") or "",
                select=True,
            )
    except Exception:
        pass

    return HTMLResponse(
        "<html><body><p>Google connected. You can close this window and return to AdFeed.</p>"
        "<script>try{window.close()}catch(e){}</script></body></html>"
    )


class GoogleMerchantSelectBody(BaseModel):
    merchant_id: str
    display_name: str = ""


@router.post("/api/app/google/merchants/select")
async def app_google_merchant_select(
    body: GoogleMerchantSelectBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db

    if not store_db.get_google_oauth_token(store.id):
        raise HTTPException(400, "Connect Google first")
    row = store_db.upsert_google_merchant_account(
        store.id,
        body.merchant_id,
        body.display_name,
        select=True,
    )
    return {"ok": True, "merchant": row}


@router.post("/api/app/google/merchants/refresh")
async def app_google_merchants_refresh(store: StoreModel = Depends(require_store)):
    from adfeed import store_db
    from adfeed.platforms.google.merchant_client import HttpMerchantClient
    from adfeed.platforms.google.oauth import access_token_for_store

    if not store_db.get_google_oauth_token(store.id):
        raise HTTPException(400, "Connect Google first")
    try:
        access, _ = access_token_for_store(store.id)
        merchants = HttpMerchantClient(access).list_merchants()
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    for m in merchants:
        store_db.upsert_google_merchant_account(
            store.id,
            m["merchant_id"],
            m.get("display_name") or "",
            select=False,
        )
    return {"ok": True, "merchants": store_db.list_google_merchant_accounts(store.id)}


@router.post("/api/app/google/disconnect")
async def app_google_disconnect(store: StoreModel = Depends(require_store)):
    from adfeed import store_db

    store_db.delete_google_oauth_token(store.id)
    return {"ok": True}


@router.get("/api/app/google/issues")
async def app_google_issues(
    store: StoreModel = Depends(require_store),
    merchant_id: Optional[str] = None,
):
    from adfeed import store_db
    from adfeed.platforms.google.issue_actions import suggest_action

    mid = (merchant_id or "").strip() or store_db.get_selected_merchant_id(store.id)
    if not mid:
        return {"merchant_id": None, "issues": [], "matched": 0, "unmatched": 0}
    issues = store_db.list_gmc_product_issues(store.id, mid)
    out = []
    matched = unmatched = 0
    for it in issues:
        action = suggest_action(it.get("reason_code") or "")["action"]
        row = dict(it)
        row["suggested_action"] = action
        if it.get("product_id_internal"):
            matched += 1
        else:
            unmatched += 1
        out.append(row)
    return {
        "merchant_id": mid,
        "issues": out,
        "matched": matched,
        "unmatched": unmatched,
    }


class GoogleIssuesSyncBody(BaseModel):
    merchant_id: Optional[str] = None
    mock_issues: Optional[list[dict]] = None


@router.post("/api/app/google/issues/sync")
async def app_google_issues_sync(
    body: GoogleIssuesSyncBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db
    from adfeed.platforms.google.merchant_client import HttpMerchantClient
    from adfeed.platforms.google.merchant_sync import sync_merchant_issues
    from adfeed.platforms.google.oauth import access_token_for_store

    mid = (body.merchant_id or "").strip() or store_db.get_selected_merchant_id(store.id)
    if not mid:
        raise HTTPException(400, "Select a Merchant account first")
    if not store_db.get_google_oauth_token(store.id) and body.mock_issues is None:
        raise HTTPException(400, "Connect Google first")

    class _Mock:
        def __init__(self, issues):
            self._issues = issues

        def list_product_issues(self, merchant_id: str):
            return self._issues

    if body.mock_issues is not None:
        client = _Mock(body.mock_issues)
    else:
        try:
            access, _ = access_token_for_store(store.id)
            client = HttpMerchantClient(access)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e

    store_db.upsert_google_merchant_account(store.id, mid, select=True)
    try:
        result = sync_merchant_issues(store.id, mid, client)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    return result


@router.get("/api/app/google/ads/metrics")
async def app_google_ads_metrics(
    store: StoreModel = Depends(require_store),
    ads_customer_id: str = "",
):
    from adfeed import store_db

    cid = (ads_customer_id or "").strip()
    if not cid:
        return {"ads_customer_id": None, "rows": [], "product_level": 0, "degraded": False}
    rows = store_db.list_ads_metrics_daily(store.id, cid)
    product_level = sum(1 for r in rows if r.get("offer_id"))
    return {
        "ads_customer_id": cid,
        "rows": rows,
        "product_level": product_level,
        "degraded": bool(rows) and product_level == 0,
    }


class GoogleAdsSyncBody(BaseModel):
    ads_customer_id: str
    mock_rows: Optional[list[dict]] = None


@router.post("/api/app/google/ads/sync")
async def app_google_ads_sync(
    body: GoogleAdsSyncBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db
    from adfeed.platforms.google.ads_client import HttpAdsMetricsClient, ads_api_configured
    from adfeed.platforms.google.ads_sync import sync_ads_metrics
    from adfeed.platforms.google.oauth import SCOPE_ADWORDS, access_token_for_store

    cid = (body.ads_customer_id or "").strip().replace("-", "")
    if not cid:
        raise HTTPException(400, "ads_customer_id required")
    tok = store_db.get_google_oauth_token(store.id)
    if not tok and body.mock_rows is None:
        raise HTTPException(400, "Connect Google first")
    if body.mock_rows is None:
        scopes = (tok or {}).get("scopes") or ""
        if SCOPE_ADWORDS not in scopes:
            raise HTTPException(403, "Reconnect Google with Ads scope")
        if not ads_api_configured():
            raise HTTPException(503, "GOOGLE_ADS_DEVELOPER_TOKEN not configured")

    class _Mock:
        def __init__(self, rows):
            self._rows = rows

        def list_product_metrics(self, ads_customer_id: str):
            return self._rows

    if body.mock_rows is not None:
        client = _Mock(body.mock_rows)
    else:
        try:
            access, _ = access_token_for_store(store.id)
            client = HttpAdsMetricsClient(access)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e

    try:
        result = sync_ads_metrics(store.id, cid, client)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    return result
