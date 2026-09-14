"""Public FastAPI routes for marketing-site tools."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field, field_validator

from adfeed.public_tools.feed_checker import (
    MAX_DOWNLOAD_BYTES,
    analyze_feed_bytes,
    analyze_feed_url,
)
from adfeed.public_tools import google_oauth as goauth
from adfeed.public_tools.google_issues import (
    demo_diagnosis,
    fetch_disapproved_issues,
    list_merchant_accounts,
)
from adfeed.public_tools.shopify_store_check import fetch_shop_products
from adfeed.public_tools.title_checker import (
    analyze_feed_titles_bytes,
    analyze_feed_titles_url,
    analyze_title,
    suggest_title_ai,
)

router = APIRouter(prefix="/api/public", tags=["public-tools"])

# Simple in-process rate limit for AI title (per client host).
_AI_HITS: dict[str, list[float]] = {}
_AI_MAX_PER_HOUR = 20


def _client_host(request: Request) -> str:
    forwarded = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip()
    if forwarded:
        return forwarded
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _allow_ai(host: str) -> bool:
    import time

    now = time.time()
    window = 3600.0
    hits = [t for t in _AI_HITS.get(host, []) if now - t < window]
    if len(hits) >= _AI_MAX_PER_HOUR:
        _AI_HITS[host] = hits
        return False
    hits.append(now)
    _AI_HITS[host] = hits
    return True


def _set_session_cookie(resp: Response, token_payload: dict) -> None:
    secure = _tools_origin().startswith("https://")
    resp.set_cookie(
        goauth.session_cookie_name(),
        goauth.mint_session_cookie(token_payload),
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=3600,
        path="/",
    )



class FeedCheckUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    max_items: int = Field(500, ge=1, le=500)

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return (v or "").strip()


class TitleCheckRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, v: str) -> str:
        return (v or "").strip()


class ShopifyCheckRequest(BaseModel):
    shop: str = Field(..., min_length=4, max_length=256)

    @field_validator("shop", mode="before")
    @classmethod
    def strip_shop(cls, v: str) -> str:
        return (v or "").strip()


class TitleFeedUrlRequest(BaseModel):
    url: str = Field(..., min_length=8, max_length=2048)
    max_items: int = Field(500, ge=1, le=500)

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return (v or "").strip()


@router.post("/title-check")
async def title_check(body: TitleCheckRequest):
    return analyze_title(body.title)


@router.post("/title-check/ai")
async def title_check_ai(request: Request, body: TitleCheckRequest):
    if not _allow_ai(_client_host(request)):
        raise HTTPException(
            status_code=429,
            detail="Too many AI title requests. Try the rule-based suggestion, or wait an hour.",
        )
    return suggest_title_ai(body.title)


@router.post("/title-check/feed")
async def title_check_feed_url(body: TitleFeedUrlRequest):
    try:
        return analyze_feed_titles_url(body.url, max_items=body.max_items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Feed download failed: {exc}") from exc


@router.post("/title-check/feed/upload")
async def title_check_feed_upload(
    file: UploadFile = File(...),
    max_items: int = Form(500),
):
    raw = await file.read()
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large")
    try:
        return analyze_feed_titles_bytes(raw, max_items=max(1, min(max_items, 500)))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/shopify-check")
async def shopify_check(body: ShopifyCheckRequest):
    try:
        return fetch_shop_products(body.shop)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Shopify check failed: {exc}") from exc


@router.post("/feed-check")
async def feed_check_url(body: FeedCheckUrlRequest):
    try:
        return analyze_feed_url(body.url, max_items=body.max_items)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Feed download failed: {exc}") from exc


@router.post("/feed-check/upload")
async def feed_check_upload(
    file: UploadFile = File(...),
    max_items: int = Form(500),
):
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(raw) > MAX_DOWNLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")
    try:
        mi = max(1, min(int(max_items or 500), 500))
        return analyze_feed_bytes(raw, max_items=mi)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _tools_origin() -> str:
    return (os.getenv("ADFEED_PUBLIC_URL") or "https://deltfu.com").rstrip("/")


@router.get("/google/oauth/start")
async def google_oauth_start():
    if not goauth.google_public_oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        url = goauth.build_authorize_url(state=goauth.mint_state())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url, status_code=302)


@router.get("/google/oauth/callback")
async def google_oauth_callback(request: Request, code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
    dest = f"{_tools_origin()}/tools/google-issues"
    if error:
        return RedirectResponse(f"{dest}?error={error}", status_code=302)
    if not code or not state or not goauth.verify_state(state):
        return RedirectResponse(f"{dest}?error=invalid_oauth", status_code=302)
    try:
        tokens = goauth.exchange_code(code)
        cookie_val = goauth.mint_session_cookie(tokens)
    except Exception as exc:
        return RedirectResponse(f"{dest}?error=token_exchange", status_code=302)

    resp = RedirectResponse(f"{dest}?connected=1", status_code=302)
    secure = _tools_origin().startswith("https://")
    resp.set_cookie(
        goauth.session_cookie_name(),
        cookie_val,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=3600,
        path="/",
    )
    return resp


@router.post("/google/logout")
async def google_logout():
    resp = Response(content='{"ok":true}', media_type="application/json")
    resp.delete_cookie(goauth.session_cookie_name(), path="/")
    return resp


@router.get("/google/status")
async def google_status(request: Request):
    session = goauth.read_session_cookie(request.cookies.get(goauth.session_cookie_name()))
    return {"connected": bool(session and session.get("access_token"))}


@router.get("/google/accounts")
async def google_accounts(request: Request):
    session = goauth.read_session_cookie(request.cookies.get(goauth.session_cookie_name()))
    if not session:
        raise HTTPException(status_code=401, detail="Connect Google first")
    try:
        access, refreshed = goauth.ensure_access_token(session)
        accounts = list_merchant_accounts(access)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    resp = JSONResponse({"ok": True, "accounts": accounts})
    if refreshed:
        _set_session_cookie(resp, refreshed)
    return resp


@router.get("/google/issues")
async def google_issues(request: Request, merchant_id: str, limit: int = 50):
    mid = (merchant_id or "").strip()
    if not mid.isdigit():
        raise HTTPException(status_code=400, detail="merchant_id must be numeric")
    session = goauth.read_session_cookie(request.cookies.get(goauth.session_cookie_name()))
    if not session:
        raise HTTPException(status_code=401, detail="Connect Google first")
    try:
        access, refreshed = goauth.ensure_access_token(session)
        report = fetch_disapproved_issues(access, mid, limit=max(1, min(limit, 100)))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    resp = JSONResponse(report)
    if refreshed:
        _set_session_cookie(resp, refreshed)
    return resp


@router.get("/google/demo/{kind}")
async def google_demo(kind: str):
    """No-auth fixtures so FEED / MIXED can be reviewed without a live MC."""
    try:
        return demo_diagnosis(kind)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
