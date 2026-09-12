"""Public routes for Google Ads monitor (marketing site only)."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse

from adfeed.public_tools import google_ads_oauth as aoauth
from adfeed.public_tools import google_ads_report as areport

router = APIRouter(prefix="/api/public/google-ads", tags=["public-google-ads"])


def _tools_origin() -> str:
    return (os.getenv("ADFEED_PUBLIC_URL") or "https://deltfu.com").rstrip("/")


def _set_cookie(resp: Response, token_payload: dict) -> None:
    secure = _tools_origin().startswith("https://")
    resp.set_cookie(
        aoauth.session_cookie_name(),
        aoauth.mint_session_cookie(token_payload),
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=3600,
        path="/",
    )


def _session(request: Request) -> dict | None:
    return aoauth.read_session_cookie(
        request.cookies.get(aoauth.session_cookie_name())
    )


@router.get("/status")
async def ads_status(request: Request):
    sess = _session(request)
    return {
        "oauth_configured": aoauth.google_ads_oauth_configured(),
        "ads_api_configured": aoauth.google_ads_api_configured(),
        "connected": bool(sess and sess.get("access_token")),
        "mode": "live" if aoauth.google_ads_api_configured() else "demo",
        "redirect_uri": aoauth.ads_redirect_uri(),
        "setup_hint": (
            "Set GOOGLE_ADS_DEVELOPER_TOKEN after Google approves Ads API access. "
            "Add redirect URI in Cloud Console: "
            + aoauth.ads_redirect_uri()
        ),
    }


@router.get("/oauth/start")
async def ads_oauth_start():
    if not aoauth.google_ads_oauth_configured():
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    try:
        url = aoauth.build_authorize_url(state=aoauth.mint_state())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return RedirectResponse(url, status_code=302)


@router.get("/oauth/callback")
async def ads_oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
):
    dest = f"{_tools_origin()}/tools/google-ads-monitor"
    if error:
        return RedirectResponse(f"{dest}?error={error}", status_code=302)
    if not code or not state or not aoauth.verify_state(state):
        return RedirectResponse(f"{dest}?error=invalid_oauth", status_code=302)
    try:
        tokens = aoauth.exchange_code(code)
        cookie_val = aoauth.mint_session_cookie(tokens)
    except Exception:
        return RedirectResponse(f"{dest}?error=token_exchange", status_code=302)

    resp = RedirectResponse(f"{dest}?connected=1", status_code=302)
    secure = _tools_origin().startswith("https://")
    resp.set_cookie(
        aoauth.session_cookie_name(),
        cookie_val,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=3600,
        path="/",
    )
    return resp


@router.post("/logout")
async def ads_logout():
    resp = Response(content='{"ok":true}', media_type="application/json")
    resp.delete_cookie(aoauth.session_cookie_name(), path="/")
    return resp


@router.get("/demo")
async def ads_demo(
    cut: str = areport.DEFAULT_CUT,
    daily_budget: float = 18.0,
    troas_target: float = 200.0,
):
    return areport.demo_report(
        cut=cut, daily_budget=daily_budget, troas_target=troas_target
    )


@router.get("/customers")
async def ads_customers(request: Request):
    if not aoauth.google_ads_api_configured():
        return {
            "ok": True,
            "mode": "demo",
            "customers": [],
            "notice": (
                "Ads API developer token not set yet — use demo report. "
                "After you have a token, reconnect Google and pick a customer."
            ),
        }
    sess = _session(request)
    if not sess:
        raise HTTPException(status_code=401, detail="Connect Google Ads first")
    try:
        access, refreshed = aoauth.ensure_access_token(sess)
        customers = areport.list_accessible_customers(access_token=access)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    payload = {"ok": True, "mode": "live", "customers": customers, "notice": ""}
    resp = JSONResponse(payload)
    if refreshed:
        _set_cookie(resp, refreshed)
    return resp


@router.get("/report")
async def ads_report(
    request: Request,
    customer_id: str = "",
    date_from: str = "2026-08-01",
    date_to: str = "2026-08-31",
    cut: str = areport.DEFAULT_CUT,
    daily_budget: float = 18.0,
    troas_target: float = 200.0,
    force_demo: int = 0,
):
    if force_demo or not aoauth.google_ads_api_configured() or not customer_id.strip():
        return areport.demo_report(
            cut=cut, daily_budget=daily_budget, troas_target=troas_target
        )

    sess = _session(request)
    if not sess:
        raise HTTPException(status_code=401, detail="Connect Google Ads first")
    try:
        access, refreshed = aoauth.ensure_access_token(sess)
        payload = areport.live_report(
            access_token=access,
            customer_id=customer_id,
            date_from=date_from,
            date_to=date_to,
            cut=cut,
            daily_budget=daily_budget,
            troas_target=troas_target,
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    resp = JSONResponse(payload)
    if refreshed:
        _set_cookie(resp, refreshed)
    return resp
