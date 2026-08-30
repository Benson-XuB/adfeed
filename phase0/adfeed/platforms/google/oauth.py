"""Google OAuth helpers for Merchant (content) + incremental Ads (adwords)."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

SCOPE_CONTENT = "https://www.googleapis.com/auth/content"
SCOPE_ADWORDS = "https://www.googleapis.com/auth/adwords"

_TOKEN_URL = "https://oauth2.googleapis.com/token"
_STATE_TTL_SEC = 600


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("GOOGLE_TOKEN_ENC_KEY") or "change-me"


def google_oauth_configured() -> bool:
    return bool(
        os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip()
        and os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip()
        and os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip()
    )


def build_authorize_url(*, state: str, include_ads: bool = False) -> str:
    if not google_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_* env not configured")
    scopes = [SCOPE_CONTENT]
    if include_ads:
        scopes.append(SCOPE_ADWORDS)
    params = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
        "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"].strip(),
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "include_granted_scopes": "true",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def scopes_for_phase(*, ads: bool) -> str:
    parts = [SCOPE_CONTENT]
    if ads:
        parts.append(SCOPE_ADWORDS)
    return " ".join(parts)


def seal_refresh_token(token: str) -> str:
    """At-rest seal with existing JWT_SECRET (opaque column refresh_token_enc)."""
    return jwt.encode(
        {"rt": token, "iat": int(time.time())},
        _jwt_secret(),
        algorithm="HS256",
    )


def open_refresh_token(sealed: str) -> str:
    payload = jwt.decode(sealed, _jwt_secret(), algorithms=["HS256"])
    rt = payload.get("rt")
    if not rt:
        raise ValueError("invalid sealed refresh token")
    return str(rt)


def make_oauth_state(store_id: str, *, phase: str = "mc") -> str:
    return jwt.encode(
        {
            "sid": store_id,
            "phase": phase if phase in ("mc", "ads") else "mc",
            "exp": int(time.time()) + _STATE_TTL_SEC,
        },
        _jwt_secret(),
        algorithm="HS256",
    )


def parse_oauth_state(state: str) -> dict[str, str]:
    try:
        payload = jwt.decode(state, _jwt_secret(), algorithms=["HS256"])
    except jwt.PyJWTError as e:
        raise ValueError("invalid oauth state") from e
    sid = str(payload.get("sid") or "").strip()
    if not sid:
        raise ValueError("oauth state missing store")
    phase = str(payload.get("phase") or "mc")
    return {"store_id": sid, "phase": phase}


def exchange_authorization_code(code: str) -> dict[str, Any]:
    if not google_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_* env not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            _TOKEN_URL,
            data={
                "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
                "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": os.environ["GOOGLE_OAUTH_REDIRECT_URI"].strip(),
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed: HTTP {resp.status_code}")
    data = resp.json()
    if not data.get("access_token"):
        raise RuntimeError("token exchange missing access_token")
    return {
        "access_token": data["access_token"],
        "refresh_token": data.get("refresh_token") or "",
        "scope": data.get("scope") or "",
        "expires_in": int(data.get("expires_in") or 0),
    }


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not google_oauth_configured():
        raise RuntimeError("GOOGLE_OAUTH_* env not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            _TOKEN_URL,
            data={
                "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"].strip(),
                "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"].strip(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"token refresh failed: HTTP {resp.status_code}")
    data = resp.json()
    if not data.get("access_token"):
        raise RuntimeError("token refresh missing access_token")
    return {
        "access_token": data["access_token"],
        "scope": data.get("scope") or "",
        "expires_in": int(data.get("expires_in") or 0),
    }


def access_token_for_store(store_id: str) -> tuple[str, str]:
    """Return (access_token, scopes) using sealed refresh token in store_db."""
    from adfeed import store_db

    tok = store_db.get_google_oauth_token(store_id)
    if not tok:
        raise RuntimeError("Google not connected")
    rt = open_refresh_token(tok["refresh_token_enc"])
    refreshed = refresh_access_token(rt)
    return refreshed["access_token"], tok.get("scopes") or refreshed.get("scope") or ""
