"""Shopify App session token verification.

App Bridge sends Authorization: Bearer <session_jwt> signed with the app secret.
Claims of interest:
  dest — https://{shop}.myshopify.com
  aud  — API key (client id)
"""

from __future__ import annotations

import os
from typing import Optional
from urllib.parse import urlparse

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import config
from . import store_db
from .store_db import Store

_security = HTTPBearer(auto_error=False)


def _normalize_shop(dest_or_domain: str) -> str:
    raw = (dest_or_domain or "").strip().lower()
    if raw.startswith("http"):
        host = urlparse(raw).hostname or ""
    else:
        host = raw
    host = host.replace("www.", "")
    if host and not host.endswith(".myshopify.com"):
        host = f"{host}.myshopify.com"
    return host


def decode_session_token(token: str) -> dict:
    """Verify Shopify session JWT. Raises jwt exceptions on failure."""
    secret = config.SHOPIFY_CLIENT_SECRET or os.getenv("SHOPIFY_API_SECRET", "")
    client_id = config.SHOPIFY_CLIENT_ID
    if not secret:
        raise jwt.InvalidTokenError("SHOPIFY_CLIENT_SECRET not configured")

    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        audience=client_id or None,
        options={
            "verify_aud": bool(client_id),
            "require": ["dest", "exp", "nbf"],
        },
    )
    return payload


def shop_from_payload(payload: dict) -> str:
    return _normalize_shop(payload.get("dest", ""))


async def require_store(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_security),
) -> Store:
    """FastAPI dependency: valid Shopify session → Store row.

    Auto-creates a store shell (no token yet) if the shop is new, so billing
    status endpoints work before product sync.
    """
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Missing Shopify session token")

    try:
        payload = decode_session_token(credentials.credentials)
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Invalid Shopify session: {e}") from e

    shop = shop_from_payload(payload)
    if not shop:
        raise HTTPException(401, "Session missing shop domain")

    store = store_db.get_store_by_domain(shop)
    if not store:
        # Ensure a system user exists for FK, then create store shell
        from .db import get_user_by_email, create_user
        sys_email = "shopify-app@adfeed.ai"
        user = get_user_by_email(sys_email) or create_user(email=sys_email, name="Shopify App")
        store = store_db.create_store(
            user_id=user.id,
            shopify_domain=shop,
            shop_name=shop.replace(".myshopify.com", ""),
        )

    request.state.shopify_payload = payload
    request.state.store = store
    return store
