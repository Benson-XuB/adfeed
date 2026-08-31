"""Merchant API dataSources — list/filter API product sources (mockable)."""

from __future__ import annotations

from typing import Any, Optional, Protocol

import httpx

_LIST_URL = (
    "https://merchantapi.googleapis.com/datasources/v1/accounts/{account}/dataSources"
)
_CREATE_URL = (
    "https://merchantapi.googleapis.com/datasources/v1/accounts/{account}/dataSources"
)

_FAKE_CI_DATA_SOURCES = [
    {
        "name": "accounts/123/dataSources/456",
        "dataSourceId": "456",
        "displayName": "API Primary (CI)",
        "input": "API",
        "primaryProductDataSource": {
            "feedLabel": "US",
            "contentLanguage": "en",
            "countries": ["US"],
        },
    }
]


def is_api_product_data_source(ds: dict) -> bool:
    """True when Input=API and type is Primary or Supplemental product source."""
    if not isinstance(ds, dict):
        return False
    input_type = str(ds.get("input") or "").strip().upper()
    if input_type != "API":
        return False
    return (
        "primaryProductDataSource" in ds
        or "primary_product_data_source" in ds
        or "supplementalProductDataSource" in ds
        or "supplemental_product_data_source" in ds
    )


def filter_api_product_data_sources(items: list[dict] | None) -> list[dict]:
    return [ds for ds in (items or []) if is_api_product_data_source(ds)]


def _is_api_primary(ds: dict) -> bool:
    return is_api_product_data_source(ds) and (
        "primaryProductDataSource" in ds or "primary_product_data_source" in ds
    )


class DataSourcesClient(Protocol):
    def list_data_sources(self, merchant_id: str) -> list[dict]:
        ...


class HttpDataSourcesClient:
    """Thin httpx client for datasources.list (+ optional create)."""

    def __init__(self, access_token: str, *, page_size: int = 100, timeout: float = 60.0):
        self._token = access_token
        self._page_size = page_size
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def list_data_sources(self, merchant_id: str) -> list[dict]:
        account = str(merchant_id).strip()
        url = _LIST_URL.format(account=account)
        page_token: str | None = None
        all_items: list[dict] = []
        with httpx.Client(timeout=self._timeout) as client:
            while True:
                params: dict[str, Any] = {"pageSize": self._page_size}
                if page_token:
                    params["pageToken"] = page_token
                resp = client.get(url, headers=self._headers(), params=params)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"dataSources.list failed: HTTP {resp.status_code} {resp.text[:300]}"
                    )
                data = resp.json()
                all_items.extend(data.get("dataSources") or data.get("data_sources") or [])
                page_token = data.get("nextPageToken") or data.get("next_page_token")
                if not page_token:
                    break
        return all_items

    def create_primary_api_data_source(
        self,
        merchant_id: str,
        *,
        display_name: str = "AdFeed API Primary",
        feed_label: str = "US",
        content_language: str = "en",
        countries: Optional[list[str]] = None,
    ) -> dict:
        account = str(merchant_id).strip()
        url = _CREATE_URL.format(account=account)
        body = {
            "displayName": display_name,
            "primaryProductDataSource": {
                "channel": "ONLINE_PRODUCTS",
                "feedLabel": feed_label,
                "contentLanguage": content_language,
                "countries": countries or [feed_label],
            },
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(url, headers=self._headers(), json=body)
        if resp.status_code >= 400:
            raise RuntimeError(
                f"dataSources.create failed: HTTP {resp.status_code} {resp.text[:300]}"
            )
        return resp.json()


def list_api_data_sources(
    merchant_id: str,
    access_token: str,
    *,
    client: Optional[DataSourcesClient] = None,
) -> list[dict]:
    """List Input=API Primary/Supplemental product dataSources for a merchant."""
    mid = str(merchant_id).strip()
    if not mid:
        raise ValueError("merchant_id required")
    c = client or HttpDataSourcesClient(access_token)
    return filter_api_product_data_sources(c.list_data_sources(mid))


def ensure_api_primary_data_source(
    merchant_id: str,
    access_token: str,
    *,
    client: Optional[Any] = None,
    **create_kwargs: Any,
) -> dict:
    """Return an existing API primary dataSource, or create one if the client supports it.

    MVP may only select from list; create is optional via mockable
    ``create_primary_api_data_source`` on the client.
    """
    mid = str(merchant_id).strip()
    if not mid:
        raise ValueError("merchant_id required")
    c = client or HttpDataSourcesClient(access_token)
    existing = filter_api_product_data_sources(c.list_data_sources(mid))
    for ds in existing:
        if _is_api_primary(ds):
            return ds
    create = getattr(c, "create_primary_api_data_source", None)
    if not callable(create):
        raise RuntimeError(
            "No API primary dataSource found; create one in Merchant Center "
            "or use a client that supports create_primary_api_data_source"
        )
    return create(mid, **create_kwargs)


def fake_ci_data_sources() -> list[dict]:
    """Deterministic list for CI mock_result=1."""
    return [dict(ds) for ds in _FAKE_CI_DATA_SOURCES]
