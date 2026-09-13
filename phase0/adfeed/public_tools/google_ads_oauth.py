"""OAuth for marketing-site Google Ads monitor (separate from MC Content API)."""

import os
import time
import re
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

# Google Ads API read access (official Ads API OAuth scope).
SCOPE_ADS = "https://www.googleapis.com/auth/adwords"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_STATE_TTL = 600
_SESSION_COOKIE = "adfeed_public_google_ads"
_SESSION_TTL = 3600


def _jwt_secret() -> str:
    return (
        os.getenv("JWT_SECRET")
        or os.getenv("GOOGLE_TOKEN_ENC_KEY")
        or "change-me-public-google-ads"
    )


def ads_redirect_uri() -> str:
    return (
        os.getenv("GOOGLE_ADS_OAUTH_REDIRECT_URI")
        or "https://deltfu.com/api/public/google-ads/oauth/callback"
    ).strip()


def google_ads_oauth_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    )


def google_ads_api_configured() -> bool:
    """Live Ads API: OAuth client is enough (Cloud project holds access level).

    Google sunset developer tokens for Ads API access (2026-09-09). The header
    is optional; access is granted on the Cloud project (Test / Explorer / …).
    """
    return google_ads_oauth_configured()


def ads_api_headers(access_token: str) -> dict[str, str]:
    """Auth headers for Google Ads REST; developer-token only if still configured."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    token = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()
    if token:
        headers["developer-token"] = token
    login_cid = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "").strip()
    if login_cid:
        digits = re.sub(r"\D", "", login_cid)
        if digits:
            headers["login-customer-id"] = digits
    return headers


def mint_state() -> str:
    return jwt.encode(
        {"purpose": "public_google_ads", "exp": int(time.time()) + _STATE_TTL},
        _jwt_secret(),
        algorithm="HS256",
    )


def verify_state(state: str) -> bool:
    try:
        payload = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
        return payload.get("purpose") == "public_google_ads"
    except Exception:
        return False


def build_authorize_url(*, state: str) -> str:
    if not google_ads_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID/SECRET not configured")
    params = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "redirect_uri": ads_redirect_uri(),
        "response_type": "code",
        "scope": SCOPE_ADS,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    data = {
        "code": code,
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        "redirect_uri": ads_redirect_uri(),
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise RuntimeError(
            f"token exchange failed: HTTP {resp.status_code} {resp.text[:200]}"
        )
    return resp.json()


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    data = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise RuntimeError(f"refresh failed: HTTP {resp.status_code} {resp.text[:200]}")
    return resp.json()


def mint_session_cookie(token_payload: dict[str, Any]) -> str:
    now = int(time.time())
    body = {
        "access_token": token_payload.get("access_token"),
        "refresh_token": token_payload.get("refresh_token"),
        "exp": now + int(token_payload.get("expires_in") or _SESSION_TTL),
        "purpose": "public_google_ads_session",
    }
    return jwt.encode(body, _jwt_secret(), algorithm="HS256")


def read_session_cookie(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        payload = jwt.decode(raw, _jwt_secret(), algorithms=["HS256"])
    except Exception:
        return None
    if payload.get("purpose") != "public_google_ads_session":
        return None
    return payload


def session_cookie_name() -> str:
    return _SESSION_COOKIE


def ensure_access_token(session: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    access = (session.get("access_token") or "").strip()
    exp = int(session.get("exp") or 0)
    if access and exp > int(time.time()) + 60:
        return access, None
    refresh = (session.get("refresh_token") or "").strip()
    if not refresh:
        if access:
            return access, None
        raise RuntimeError("Google Ads session expired; connect again")
    refreshed = refresh_access_token(refresh)
    if not refreshed.get("refresh_token"):
        refreshed["refresh_token"] = refresh
    return refreshed["access_token"], refreshed
