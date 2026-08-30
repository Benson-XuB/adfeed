"""Meta (Facebook) OAuth for Catalog management."""

from __future__ import annotations

import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx
import jwt

SCOPE_CATALOG = "catalog_management"
SCOPE_BUSINESS = "business_management"
DEFAULT_SCOPES = f"{SCOPE_CATALOG},{SCOPE_BUSINESS}"


def _graph_version() -> str:
    return os.getenv("META_GRAPH_VERSION", "v21.0").strip() or "v21.0"


def _jwt_secret() -> str:
    return os.getenv("JWT_SECRET") or os.getenv("META_TOKEN_ENC_KEY") or "change-me"


def meta_oauth_configured() -> bool:
    return bool(
        os.getenv("META_APP_ID", "").strip()
        and os.getenv("META_APP_SECRET", "").strip()
        and os.getenv("META_OAUTH_REDIRECT_URI", "").strip()
    )


def seal_access_token(token: str) -> str:
    return jwt.encode(
        {"at": token, "iat": int(time.time())},
        _jwt_secret(),
        algorithm="HS256",
    )


def open_access_token(sealed: str) -> str:
    payload = jwt.decode(sealed, _jwt_secret(), algorithms=["HS256"])
    at = payload.get("at")
    if not at:
        raise ValueError("invalid sealed access token")
    return str(at)


def make_oauth_state(store_id: str) -> str:
    return jwt.encode(
        {"sid": store_id, "plat": "meta", "exp": int(time.time()) + 600},
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
    if not meta_oauth_configured():
        raise RuntimeError("META_* env not configured")
    params = {
        "client_id": os.environ["META_APP_ID"].strip(),
        "redirect_uri": os.environ["META_OAUTH_REDIRECT_URI"].strip(),
        "state": state,
        "response_type": "code",
        "scope": DEFAULT_SCOPES,
    }
    return f"https://www.facebook.com/{_graph_version()}/dialog/oauth?" + urlencode(params)


def exchange_authorization_code(code: str) -> dict[str, Any]:
    if not meta_oauth_configured():
        raise RuntimeError("META_* env not configured")
    ver = _graph_version()
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(
            f"https://graph.facebook.com/{ver}/oauth/access_token",
            params={
                "client_id": os.environ["META_APP_ID"].strip(),
                "client_secret": os.environ["META_APP_SECRET"].strip(),
                "redirect_uri": os.environ["META_OAUTH_REDIRECT_URI"].strip(),
                "code": code,
            },
        )
    if resp.status_code != 200:
        raise RuntimeError(f"Meta token exchange failed: HTTP {resp.status_code}")
    data = resp.json()
    short = data.get("access_token")
    if not short:
        raise RuntimeError("Meta token exchange missing access_token")
    # Exchange for long-lived user token when possible
    with httpx.Client(timeout=30.0) as client:
        long_resp = client.get(
            f"https://graph.facebook.com/{ver}/oauth/access_token",
            params={
                "grant_type": "fb_exchange_token",
                "client_id": os.environ["META_APP_ID"].strip(),
                "client_secret": os.environ["META_APP_SECRET"].strip(),
                "fb_exchange_token": short,
            },
        )
    token = short
    if long_resp.status_code == 200 and long_resp.json().get("access_token"):
        token = long_resp.json()["access_token"]
    return {
        "access_token": token,
        "scopes": DEFAULT_SCOPES.replace(",", " "),
    }


def access_token_for_store(store_id: str) -> str:
    from adfeed import store_db

    tok = store_db.get_meta_oauth_token(store_id)
    if not tok:
        raise RuntimeError("Meta not connected")
    return open_access_token(tok["access_token_enc"])
