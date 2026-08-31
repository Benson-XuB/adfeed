"""FastAPI routes for Google Merchant / Ads read loop."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from adfeed.shopify_auth import require_store
from adfeed.store_db import Store as StoreModel

router = APIRouter(tags=["google"])


def google_push_enabled() -> bool:
    """Truthy env gate for sandbox Merchant API push (1/true/yes)."""
    return (os.getenv("GOOGLE_PUSH_ENABLED") or "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


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
    ads_settings = store_db.get_google_ads_settings(store.id) or {}
    return {
        "oauth_configured": google_oauth_configured(),
        "ads_api_configured": ads_api_configured(),
        "connected": bool(tok),
        "scopes": scopes,
        "has_content_scope": SCOPE_CONTENT in scopes,
        "has_ads_scope": SCOPE_ADWORDS in scopes,
        "merchants": merchants,
        "selected_merchant_id": store_db.get_selected_merchant_id(store.id),
        "push_enabled": google_push_enabled(),
        "ads_customer_id": ads_settings.get("ads_customer_id"),
        "ads_window_days": ads_settings.get("window_days") or 7,
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
    window_days: int = 7,
):
    from adfeed import store_db
    from adfeed.platforms.google.ads_client import normalize_window_days

    cid = (ads_customer_id or "").strip()
    wd = normalize_window_days(window_days)
    if not cid:
        return {
            "ads_customer_id": None,
            "window_days": wd,
            "rows": [],
            "product_level": 0,
            "degraded": False,
            "summary": {
                "impressions": 0,
                "clicks": 0,
                "cost_micros": 0,
                "conversions": 0.0,
            },
        }
    rows = store_db.list_ads_metrics_daily(store.id, cid, window_days=wd)
    product_level = sum(1 for r in rows if r.get("offer_id"))
    summary = {
        "impressions": sum(int(r.get("impressions") or 0) for r in rows),
        "clicks": sum(int(r.get("clicks") or 0) for r in rows),
        "cost_micros": sum(int(r.get("cost_micros") or 0) for r in rows),
        "conversions": float(sum(float(r.get("conversions") or 0) for r in rows)),
    }
    return {
        "ads_customer_id": cid,
        "window_days": wd,
        "rows": rows,
        "product_level": product_level,
        "degraded": bool(rows) and product_level == 0,
        "summary": summary,
    }


@router.get("/api/app/google/ads/settings")
async def app_google_ads_settings(store: StoreModel = Depends(require_store)):
    from adfeed import store_db

    settings = store_db.get_google_ads_settings(store.id)
    if not settings:
        return {
            "ads_customer_id": None,
            "window_days": 7,
        }
    return {
        "ads_customer_id": settings.get("ads_customer_id"),
        "window_days": int(settings.get("window_days") or 7),
        "updated_at": settings.get("updated_at"),
    }


class GoogleAdsSyncBody(BaseModel):
    ads_customer_id: str
    window_days: int = 7
    mock_rows: Optional[list[dict]] = None


@router.post("/api/app/google/ads/sync")
async def app_google_ads_sync(
    body: GoogleAdsSyncBody,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db
    from adfeed.platforms.google.ads_client import (
        HttpAdsMetricsClient,
        ads_api_configured,
        normalize_window_days,
    )
    from adfeed.platforms.google.ads_sync import sync_ads_metrics
    from adfeed.platforms.google.oauth import SCOPE_ADWORDS, access_token_for_store

    cid = (body.ads_customer_id or "").strip().replace("-", "")
    if not cid:
        raise HTTPException(400, "ads_customer_id required")
    wd = normalize_window_days(body.window_days)
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

        def list_product_metrics(self, ads_customer_id: str, window_days: int = 7):
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
        result = sync_ads_metrics(store.id, cid, client, window_days=wd)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    store_db.upsert_google_ads_settings(
        store.id, ads_customer_id=cid, window_days=wd
    )
    return result


class GoogleDataSourceSelectBody(BaseModel):
    data_source_name: str
    merchant_id: Optional[str] = None
    # CI: list of dataSource dicts, or truthy 1/true to use fake_ci_data_sources
    mock_result: Optional[Any] = None


def _resolve_mock_data_sources(mock_result: Any) -> Optional[list[dict]]:
    """Return mock list when mock_result is set; None means use live API."""
    from adfeed.platforms.google.datasources import fake_ci_data_sources

    if mock_result is None:
        return None
    if isinstance(mock_result, str):
        raw = mock_result.strip()
        if not raw:
            return None
        if raw.lower() in ("1", "true", "yes"):
            return fake_ci_data_sources()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(400, f"mock_result must be JSON or 1: {e}") from e
        if not isinstance(parsed, list):
            raise HTTPException(400, "mock_result JSON must be a list")
        return parsed
    if isinstance(mock_result, (int, bool)):
        if mock_result:
            return fake_ci_data_sources()
        return None
    if isinstance(mock_result, list):
        return mock_result
    raise HTTPException(400, "mock_result must be a list, 1/true, or JSON string")


@router.get("/api/app/google/datasources")
async def app_google_datasources(
    store: StoreModel = Depends(require_store),
    merchant_id: Optional[str] = None,
    mock_result: Optional[str] = None,
):
    """List API Input Primary/Supplemental dataSources for the selected merchant.

    ``mock_result`` query: ``1`` / ``true`` uses a fixed CI list; a JSON array
    string is returned as-is (still gated by OAuth).
    """
    from adfeed import store_db
    from adfeed.platforms.google.datasources import list_api_data_sources
    from adfeed.platforms.google.oauth import access_token_for_store

    if not store_db.get_google_oauth_token(store.id):
        raise HTTPException(400, "Connect Google first")

    mid = (merchant_id or "").strip() or store_db.get_selected_merchant_id(store.id)
    if not mid:
        raise HTTPException(400, "Select a Merchant account first")

    mock_sources = _resolve_mock_data_sources(mock_result)
    if mock_sources is not None:
        return {"merchant_id": mid, "data_sources": mock_sources}

    try:
        access, _ = access_token_for_store(store.id)
        sources = list_api_data_sources(mid, access)
    except RuntimeError as e:
        raise HTTPException(502, str(e)) from e
    return {"merchant_id": mid, "data_sources": sources}


@router.post("/api/app/google/datasources/select")
async def app_google_datasources_select(
    body: GoogleDataSourceSelectBody,
    store: StoreModel = Depends(require_store),
):
    """Persist selected API dataSource name on the merchant row (OAuth required).

    Name must appear in the API-filtered list (or mock_result list for CI).
    """
    from adfeed import store_db
    from adfeed.platforms.google.datasources import (
        filter_api_product_data_sources,
        list_api_data_sources,
    )
    from adfeed.platforms.google.oauth import access_token_for_store

    if not store_db.get_google_oauth_token(store.id):
        raise HTTPException(400, "Connect Google first")

    mid = (body.merchant_id or "").strip() or store_db.get_selected_merchant_id(store.id)
    if not mid:
        raise HTTPException(400, "Select a Merchant account first")

    ds = (body.data_source_name or "").strip()
    if not ds:
        raise HTTPException(400, "data_source_name required")

    mock_sources = _resolve_mock_data_sources(body.mock_result)
    if mock_sources is not None:
        # CI path: allow names from the provided mock list (still filter to API shape when possible)
        allowed = filter_api_product_data_sources(mock_sources)
        if not allowed:
            # mock list may be bare name-only dicts for tests
            allowed = [s for s in mock_sources if isinstance(s, dict) and (s.get("name") or "").strip()]
        allowed_names = {(s.get("name") or "").strip() for s in allowed}
    else:
        try:
            access, _ = access_token_for_store(store.id)
            allowed = list_api_data_sources(mid, access)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e
        allowed_names = {(s.get("name") or "").strip() for s in allowed}

    if ds not in allowed_names:
        raise HTTPException(400, "dataSource not in API list for this merchant")

    try:
        row = store_db.set_merchant_data_source(store.id, mid, ds)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"ok": True, "merchant": row}


class GooglePushBody(BaseModel):
    rows: Optional[list[dict[str, Any]]] = None
    mock_result: Optional[dict] = None
    use_fake: bool = False
    merchant_id: Optional[str] = None
    channel: str = "online"
    content_language: str = "en"
    feed_label: str = "US"


class _FakeProductPushClient:
    """CI / sandbox stub — always succeeds without calling Google."""

    def insert_product_input(
        self,
        *,
        merchant_id: str,
        data_source: str,
        product_input: dict,
    ) -> dict:
        offer = product_input.get("offerId") or ""
        return {
            "name": f"accounts/{merchant_id}/productInputs/{offer}",
            "offerId": offer,
        }


@router.post("/api/app/google/push")
async def app_google_push(
    body: GooglePushBody,
    store: StoreModel = Depends(require_store),
):
    """Push canonical rows to Merchant productInputs (feature-flagged)."""
    from adfeed import store_db
    from adfeed.platforms.google.oauth import access_token_for_store
    from adfeed.platforms.google.product_push import (
        LiveProductPushClient,
        push_canonical_rows,
    )

    if not google_push_enabled():
        raise HTTPException(503, "Google push is disabled (GOOGLE_PUSH_ENABLED).")

    mid = (body.merchant_id or "").strip() or store_db.get_selected_merchant_id(store.id)
    if not mid:
        raise HTTPException(400, "Select a Merchant account first")

    merchants = {
        m["merchant_id"]: m for m in store_db.list_google_merchant_accounts(store.id)
    }
    merchant = merchants.get(mid)
    if not merchant:
        raise HTTPException(400, "Merchant account not found")
    data_source = (merchant.get("data_source_name") or "").strip()
    if not data_source:
        raise HTTPException(400, "Select an API dataSource first")

    if body.rows is None or (isinstance(body.rows, list) and len(body.rows) == 0):
        from adfeed.pipeline import build_feed_rows_for_store

        country = (body.feed_label or "US").strip().upper() or "US"
        rows = build_feed_rows_for_store(store.id, country=country)
        if not rows:
            raise HTTPException(
                400,
                "No feed rows to push — enable ready products for this store, or pass rows.",
            )
    else:
        rows = body.rows

    use_fake = bool(body.use_fake) or body.mock_result is not None
    if not use_fake and not store_db.get_google_oauth_token(store.id):
        raise HTTPException(400, "Connect Google first")

    if use_fake:
        client = _FakeProductPushClient()
    else:
        try:
            access, _ = access_token_for_store(store.id)
            client = LiveProductPushClient(access)
        except RuntimeError as e:
            raise HTTPException(502, str(e)) from e

    try:
        result = push_canonical_rows(
            store.id,
            mid,
            data_source,
            rows,
            client=client,
            channel=body.channel or "online",
            content_language=body.content_language or "en",
            feed_label=body.feed_label or "US",
        )
    except (RuntimeError, ValueError) as e:
        raise HTTPException(502, str(e)) from e
    return result


@router.get("/api/app/google/push/runs/{run_id}")
async def app_google_push_run(
    run_id: str,
    store: StoreModel = Depends(require_store),
):
    from adfeed import store_db

    if not google_push_enabled():
        raise HTTPException(503, "Google push is disabled (GOOGLE_PUSH_ENABLED).")

    run = store_db.get_push_run(run_id)
    if not run or run.get("store_id") != store.id:
        raise HTTPException(404, "Push run not found")
    items = store_db.list_push_items(run_id)
    return {**run, "items": items}
