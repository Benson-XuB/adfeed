"""TikTok Shop Partner OAuth helpers."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

_STATE_TTL = 600


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("TIKTOK_TOKEN_ENC_KEY") or "change-me"


def tiktok_oauth_configured() -> bool:
    return bool(
        os.getenv("TIKTOK_CLIENT_KEY", "").strip()
        and os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
        and os.getenv("TIKTOK_OAUTH_REDIRECT_URI", "").strip()
    )


def seal_token(token: str) -> str:
    return jwt.encode(
        {"t": token, "iat": int(time.time())},
        _jwt_secret(),
        algorithm="HS256",
    )


def open_token(sealed: str) -> str:
    payload = jwt.decode(sealed, _jwt_secret(), algorithms=["HS256"])
    t = payload.get("t")
    if not t:
        raise ValueError("invalid sealed token")
    return str(t)


def make_oauth_state(store_id: str) -> str:
    return jwt.encode(
        {"sid": store_id, "plat": "tiktok", "exp": int(time.time()) + _STATE_TTL},
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
    return {"store_id": sid}


def build_authorize_url(*, state: str) -> str:
    if not tiktok_oauth_configured():
        raise RuntimeError("TIKTOK_* env not configured")
    params = {
        "app_key": os.environ["TIKTOK_CLIENT_KEY"].strip(),
        "state": state,
    }
    redirect = os.environ["TIKTOK_OAUTH_REDIRECT_URI"].strip()
    if redirect:
        params["redirect_uri"] = redirect
    return "https://auth.tiktok-shops.com/oauth/authorize?" + urlencode(params)


def exchange_authorization_code(code: str) -> dict[str, Any]:
    if not tiktok_oauth_configured():
        raise RuntimeError("TIKTOK_* env not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            "https://auth.tiktok-shops.com/api/v2/token/get",
            json={
                "app_key": os.environ["TIKTOK_CLIENT_KEY"].strip(),
                "app_secret": os.environ["TIKTOK_CLIENT_SECRET"].strip(),
                "auth_code": code,
                "grant_type": "authorized_code",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"TikTok token exchange failed: HTTP {resp.status_code}")
    body = resp.json()
    data = body.get("data") or body
    access = data.get("access_token") or ""
    refresh = data.get("refresh_token") or ""
    if not access and not refresh:
        raise RuntimeError("TikTok token exchange missing tokens")
    return {
        "access_token": access,
        "refresh_token": refresh or access,
        "scopes": str(data.get("scope") or ""),
    }


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    if not tiktok_oauth_configured():
        raise RuntimeError("TIKTOK_* env not configured")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            "https://auth.tiktok-shops.com/api/v2/token/refresh",
            json={
                "app_key": os.environ["TIKTOK_CLIENT_KEY"].strip(),
                "app_secret": os.environ["TIKTOK_CLIENT_SECRET"].strip(),
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"TikTok token refresh failed: HTTP {resp.status_code}")
    body = resp.json()
    data = body.get("data") or body
    access = data.get("access_token") or ""
    refresh = data.get("refresh_token") or refresh_token
    if not access:
        raise RuntimeError("TikTok token refresh missing access_token")
    return {
        "access_token": access,
        "refresh_token": refresh,
        "scopes": str(data.get("scope") or ""),
    }


def access_token_for_store(store_id: str) -> str:
    from adfeed import store_db

    tok = store_db.get_tiktok_oauth_token(store_id)
    if not tok:
        raise RuntimeError("TikTok not connected")
    # Prefer sealed access; refresh if we only have refresh
    at_enc = tok.get("access_token_enc") or ""
    rt_enc = tok.get("refresh_token_enc") or ""
    if at_enc:
        try:
            return open_token(at_enc)
        except Exception:
            pass
    if not rt_enc:
        raise RuntimeError("TikTok tokens missing")
    refreshed = refresh_access_token(open_token(rt_enc))
    store_db.upsert_tiktok_oauth_token(
        store_id,
        seal_token(refreshed["refresh_token"]),
        seal_token(refreshed["access_token"]),
        refreshed.get("scopes") or tok.get("scopes") or "",
    )
    return refreshed["access_token"]
