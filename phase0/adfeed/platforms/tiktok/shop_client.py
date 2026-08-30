"""TikTok Shop Partner client — list shops + register feed URL (P3)."""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from typing import Any
from urllib.parse import urlencode

import httpx


def _api_base() -> str:
    return (
        os.getenv("TIKTOK_API_BASE", "https://open-api.tiktokglobalshop.com").rstrip("/")
    )


def shops_from_payload(payload: dict) -> list[dict]:
    data = payload.get("data") or payload
    shops = data.get("shops") or data.get("shop_list") or []
    if isinstance(data, list):
        shops = data
    out: list[dict] = []
    for item in shops or []:
        sid = str(
            item.get("id")
            or item.get("shop_id")
            or item.get("shop_code")
            or ""
        ).strip()
        if not sid:
            continue
        out.append(
            {
                "shop_id": sid,
                "display_name": str(
                    item.get("name") or item.get("shop_name") or sid
                ),
                "cipher": str(item.get("cipher") or item.get("shop_cipher") or ""),
            }
        )
    return out


def sign_request(
    app_secret: str,
    *,
    path: str,
    params: dict[str, str],
    body: str = "",
) -> str:
    """TikTok Shop style sign: HMAC-SHA256 over sorted query + path (+ body)."""
    items = sorted((k, v) for k, v in params.items() if k != "sign" and v is not None)
    base = path + "".join(f"{k}{v}" for k, v in items) + (body or "")
    return hmac.new(
        app_secret.encode("utf-8"),
        base.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


class HttpTikTokShopClient:
    def __init__(self, access_token: str, *, app_key: str | None = None, app_secret: str | None = None):
        self._token = access_token
        self._app_key = (app_key or os.getenv("TIKTOK_CLIENT_KEY", "")).strip()
        self._app_secret = (app_secret or os.getenv("TIKTOK_CLIENT_SECRET", "")).strip()

    def list_shops(self) -> list[dict]:
        path = "/authorization/202309/shops"
        ts = str(int(time.time()))
        params = {
            "app_key": self._app_key,
            "timestamp": ts,
        }
        if self._app_secret:
            params["sign"] = sign_request(self._app_secret, path=path, params=params)
        url = f"{_api_base()}{path}?{urlencode(params)}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(
                url,
                headers={"x-tts-access-token": self._token, "Content-Type": "application/json"},
            )
        if resp.status_code != 200:
            raise RuntimeError(
                f"TikTok list shops failed: HTTP {resp.status_code} {resp.text[:200]}"
            )
        return shops_from_payload(resp.json())

    def register_feed_url(self, shop_id: str, feed_url: str) -> dict[str, Any]:
        """P3: no Shop schedule-URL API like Meta — return registration payload for DB."""
        return {
            "shop_id": shop_id,
            "feed_url": feed_url,
            "mode": "register",
            "note": "TikTok Shop has no scheduled URL fetch; CSV URL registered for merchant/API follow-up.",
        }
