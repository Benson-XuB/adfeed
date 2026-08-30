"""Meta Graph Catalog + Product Feed client (httpx)."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx


def _graph_version() -> str:
    return os.getenv("META_GRAPH_VERSION", "v21.0").strip() or "v21.0"


def catalogs_from_graph_payload(payload: dict) -> list[dict]:
    out: list[dict] = []
    for item in payload.get("data") or []:
        cid = str(item.get("id") or "").strip()
        if not cid:
            continue
        out.append(
            {
                "catalog_id": cid,
                "display_name": str(item.get("name") or cid),
            }
        )
    return out


class HttpMetaCatalogClient:
    def __init__(self, access_token: str):
        self._token = access_token

    def _get(self, path: str, params: dict | None = None) -> dict:
        q = dict(params or {})
        q["access_token"] = self._token
        url = f"https://graph.facebook.com/{_graph_version()}{path}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(url, params=q)
        if resp.status_code != 200:
            raise RuntimeError(f"Meta GET {path} failed: HTTP {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def _post(self, path: str, data: dict) -> dict:
        body = dict(data)
        body["access_token"] = self._token
        url = f"https://graph.facebook.com/{_graph_version()}{path}"
        with httpx.Client(timeout=60.0) as client:
            resp = client.post(url, data=body)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Meta POST {path} failed: HTTP {resp.status_code} {resp.text[:300]}")
        return resp.json()

    def list_catalogs(self) -> list[dict]:
        """Prefer business-owned catalogs; fall back to /me owned edges."""
        catalogs: list[dict] = []
        seen: set[str] = set()
        try:
            businesses = self._get("/me/businesses", {"fields": "id,name"})
            for biz in businesses.get("data") or []:
                bid = biz.get("id")
                if not bid:
                    continue
                owned = self._get(
                    f"/{bid}/owned_product_catalogs",
                    {"fields": "id,name"},
                )
                for c in catalogs_from_graph_payload(owned):
                    if c["catalog_id"] not in seen:
                        seen.add(c["catalog_id"])
                        catalogs.append(c)
        except RuntimeError:
            pass
        if not catalogs:
            try:
                mine = self._get("/me/product_catalogs", {"fields": "id,name"})
                for c in catalogs_from_graph_payload(mine):
                    if c["catalog_id"] not in seen:
                        seen.add(c["catalog_id"])
                        catalogs.append(c)
            except RuntimeError:
                pass
        return catalogs

    def attach_scheduled_feed(
        self,
        catalog_id: str,
        *,
        feed_url: str,
        feed_name: str = "AdFeed AI",
        hour: int = 3,
    ) -> dict[str, Any]:
        """Create a product feed that Meta fetches daily from our public URL."""
        schedule = json.dumps(
            {
                "interval": "DAILY",
                "url": feed_url,
                "hour": str(int(hour)),
            }
        )
        created = self._post(
            f"/{catalog_id}/product_feeds",
            {
                "name": feed_name,
                "schedule": schedule,
            },
        )
        feed_id = str(created.get("id") or "")
        if not feed_id:
            raise RuntimeError("Meta product_feeds create missing id")
        # Best-effort immediate fetch
        try:
            self._post(f"/{feed_id}/uploads", {"url": feed_url})
        except RuntimeError:
            pass
        return {"product_feed_id": feed_id, "catalog_id": catalog_id, "feed_url": feed_url}
