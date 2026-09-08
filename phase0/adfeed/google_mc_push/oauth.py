"""App-scoped Google OAuth for MC Push (separate redirect from marketing public tools)."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
import jwt

SCOPE_CONTENT = "https://www.googleapis.com/auth/content"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_STATE_TTL = 600


def _jwt_secret() -> str:
    return (
        os.getenv("JWT_SECRET")
        or os.getenv("GOOGLE_TOKEN_ENC_KEY")
        or "change-me-app-google"
    )


def app_redirect_uri() -> str:
    return (
        os.getenv("GOOGLE_APP_OAUTH_REDIRECT_URI")
        or os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
        or "http://127.0.0.1:8000/api/app/google/oauth/callback"
    ).strip()


def google_oauth_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
    )


def mint_state(store_id: str) -> str:
    return jwt.encode(
        {
            "purpose": "app_google",
            "store_id": store_id,
            "exp": int(time.time()) + _STATE_TTL,
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def verify_state(state: str) -> Optional[str]:
    """Return store_id if state is valid."""
    try:
        payload = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
    except Exception:
        return None
    if payload.get("purpose") != "app_google":
        return None
    sid = str(payload.get("store_id") or "").strip()
    return sid or None


def build_authorize_url(*, store_id: str) -> str:
    if not google_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_CLIENT_ID/SECRET not configured")
    params = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "redirect_uri": app_redirect_uri(),
        "response_type": "code",
        "scope": SCOPE_CONTENT,
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": mint_state(store_id),
    }
    return f"{_AUTH_URL}?{urlencode(params)}"


def exchange_code(code: str) -> dict[str, Any]:
    data = {
        "code": code,
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
        "redirect_uri": app_redirect_uri(),
        "grant_type": "authorization_code",
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(_TOKEN_URL, data=data)
    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed: HTTP {resp.status_code} {resp.text[:200]}")
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


def expiry_iso_from_expires_in(expires_in: Any) -> str:
    try:
        seconds = int(expires_in or 3600)
    except (TypeError, ValueError):
        seconds = 3600
    ts = datetime.now(timezone.utc).timestamp() + max(60, seconds)
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_store_access_token(conn: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    """Return access token; optionally patched fields to upsert."""
    access = (conn.get("access_token") or "").strip()
    expiry = (conn.get("token_expiry") or "").strip()
    now = datetime.now(timezone.utc)
    still_good = False
    if access and expiry:
        try:
            exp_dt = datetime.strptime(expiry.replace("Z", "+0000"), "%Y-%m-%dT%H:%M:%S%z")
            still_good = exp_dt > now.astimezone(timezone.utc).replace(tzinfo=exp_dt.tzinfo)
            # simpler compare via timestamp
            still_good = exp_dt.timestamp() > now.timestamp() + 60
        except ValueError:
            still_good = bool(access)
    if still_good:
        return access, None
    refresh = (conn.get("refresh_token") or "").strip()
    if not refresh:
        if access:
            return access, None
        raise RuntimeError("Google session expired; connect again")
    refreshed = refresh_access_token(refresh)
    patch = {
        "access_token": refreshed["access_token"],
        "token_expiry": expiry_iso_from_expires_in(refreshed.get("expires_in")),
        "refresh_token": refreshed.get("refresh_token") or refresh,
    }
    return patch["access_token"], patch
