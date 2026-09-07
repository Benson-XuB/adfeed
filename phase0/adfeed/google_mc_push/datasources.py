"""Ensure an AdFeed API primary data source exists for productInputs.insert."""

from __future__ import annotations

from typing import Any, Optional

import httpx

_DS_BASE = "https://merchantapi.googleapis.com/datasources/v1/accounts/{account}/dataSources"
_ADFEED_NAME = "AdFeed"


def list_data_sources(access_token: str, merchant_id: str) -> list[dict[str, Any]]:
    url = _DS_BASE.format(account=str(merchant_id).strip())
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"dataSources.list failed: HTTP {resp.status_code} {resp.text[:300]}")
    return list(resp.json().get("dataSources") or [])


def _datasource_id(name: str) -> str:
    # accounts/123/dataSources/456 → 456
    return str(name or "").rstrip("/").split("/")[-1]


def find_adfeed_api_source(sources: list[dict[str, Any]]) -> Optional[dict[str, str]]:
    for src in sources or []:
        display = str(src.get("displayName") or "").strip()
        if display != _ADFEED_NAME:
            continue
        # Prefer primary product sources that are not file-input oriented.
        # API sources typically lack fileInput; have primaryProductDataSource.
        if src.get("fileInput"):
            continue
        name = str(src.get("name") or "")
        ds_id = _datasource_id(name)
        if not ds_id:
            continue
        return {"data_source_id": ds_id, "data_source_name": display, "name": name}
    return None


def create_adfeed_api_source(
    access_token: str,
    merchant_id: str,
    *,
    content_language: str = "en",
    feed_label: str = "US",
    country: str = "US",
) -> dict[str, str]:
    url = _DS_BASE.format(account=str(merchant_id).strip())
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    body = {
        "displayName": _ADFEED_NAME,
        "primaryProductDataSource": {
            "channel": "ONLINE_PRODUCTS",
            "countries": [country.upper()],
            "contentLanguage": content_language,
            "feedLabel": feed_label,
        },
    }
    with httpx.Client(timeout=60.0) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"dataSources.create failed: HTTP {resp.status_code} {resp.text[:400]}")
    data = resp.json()
    name = str(data.get("name") or "")
    ds_id = _datasource_id(name)
    if not ds_id:
        raise RuntimeError("dataSources.create returned no name")
    return {"data_source_id": ds_id, "data_source_name": _ADFEED_NAME, "name": name}


def ensure_adfeed_data_source(
    access_token: str,
    merchant_id: str,
    *,
    content_language: str = "en",
    feed_label: str = "US",
    country: str = "US",
) -> dict[str, str]:
    existing = find_adfeed_api_source(list_data_sources(access_token, merchant_id))
    if existing:
        return existing
    return create_adfeed_api_source(
        access_token,
        merchant_id,
        content_language=content_language,
        feed_label=feed_label,
        country=country,
    )
