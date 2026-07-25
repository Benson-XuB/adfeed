"""认证模块 — Google OAuth 2.0 + Magic Link + JWT"""
import os, time, jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from pathlib import Path

import httpx

from .db import User, get_user_by_email, get_user_by_google_id, create_user, update_user

JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production-" + str(hash(str(Path(__file__)))))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 24 * 7  # 一周

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:3000/auth/callback")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")


# ═══════════════ JWT ═══════════════

def create_jwt(user_id: str, email: str) -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


# ═══════════════ Google OAuth ═══════════════

def get_google_auth_url(state: str = "login") -> str:
    from urllib.parse import urlencode
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


async def exchange_google_code(code: str) -> Optional[dict]:
    """用授权码换 token，返回 {email, name, google_id, avatar_url} 或 None"""
    try:
        async with httpx.AsyncClient() as client:
            # Step 1: 换 access_token
            token_resp = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": GOOGLE_REDIRECT_URI,
                },
            )
            if token_resp.status_code != 200:
                return None
            token_data = token_resp.json()
            access_token = token_data.get("access_token")

            # Step 2: 换取用户信息
            user_resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                return None
            info = user_resp.json()
            return {
                "email": info.get("email", ""),
                "name": info.get("name", ""),
                "google_id": info.get("id", ""),
                "avatar_url": info.get("picture", ""),
            }
    except Exception:
        return None


async def google_login(code: str) -> Optional[tuple[User, str]]:
    """Google OAuth 登录/注册，返回 (User, jwt_token) 或 None"""
    info = await exchange_google_code(code)
    if not info or not info.get("email"):
        return None

    user = get_user_by_google_id(info["google_id"])
    if not user:
        user = get_user_by_email(info["email"])
        if user:
            # 已有邮箱账号，绑定 Google
            update_user(user.id, google_id=info["google_id"], avatar_url=info.get("avatar_url"))
        else:
            user = create_user(
                email=info["email"],
                google_id=info["google_id"],
                name=info.get("name"),
                avatar_url=info.get("avatar_url"),
            )

    token = create_jwt(user.id, user.email)
    return user, token


# ═══════════════ Magic Link ═══════════════

from .db import create_magic_link as _create_magic_link, verify_magic_link as _verify_magic_link


async def send_magic_link_email(email: str, token: str):
    """TODO: 接入真实邮件服务 (Resend/SendGrid)"""
    link = f"{BASE_URL}/auth/magic-link?token={token}"
    print(f"[Magic Link] {email} -> {link}")


def verify_magic_link_and_login(token: str) -> Optional[tuple[User, str]]:
    email = _verify_magic_link(token)
    if not email:
        return None
    user = get_user_by_email(email)
    if not user:
        user = create_user(email=email)
    jwt_token = create_jwt(user.id, user.email)
    return user, jwt_token
