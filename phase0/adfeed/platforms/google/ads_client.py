"""Live Google Ads metrics client (REST search) — read-only Search only."""

from __future__ import annotations

import os
from typing import Any

import httpx

# Pin a stable Ads API version; bump intentionally when Google deprecates.
_ADS_API_VERSION = os.getenv("GOOGLE_ADS_API_VERSION", "v19")
_SEARCH = (
    f"https://googleads.googleapis.com/{_ADS_API_VERSION}/"
    "customers/{customer_id}/googleAds:search"
)

_PRODUCT_GAQL = """
SELECT
  segments.date,
  segments.product_item_id,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM shopping_performance_view
WHERE segments.date DURING LAST_7_DAYS
""".strip()

_CAMPAIGN_FALLBACK_GAQL = """
SELECT
  segments.date,
  campaign.id,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
""".strip()


def metrics_from_search_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows or []:
        segs = row.get("segments") or {}
        metrics = row.get("metrics") or {}
        campaign = row.get("campaign") or {}
        offer = str(
            segs.get("productItemId") or segs.get("product_item_id") or ""
        ).strip()
        date = str(segs.get("date") or "")
        cid = str(campaign.get("id") or "").strip() or None
        out.append(
            {
                "date": date,
                "offer_id": offer or None,
                "campaign_id": cid,
                "impressions": int(metrics.get("impressions") or 0),
                "clicks": int(metrics.get("clicks") or 0),
                "cost_micros": int(metrics.get("costMicros") or metrics.get("cost_micros") or 0),
                "conversions": float(metrics.get("conversions") or 0),
            }
        )
    return out


def ads_developer_token() -> str:
    return os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "").strip()


def ads_api_configured() -> bool:
    return bool(ads_developer_token())


class HttpAdsMetricsClient:
    def __init__(
        self,
        access_token: str,
        *,
        developer_token: str | None = None,
        login_customer_id: str | None = None,
    ):
        self._token = access_token
        self._dev = (developer_token if developer_token is not None else ads_developer_token()).strip()
        self._login = (login_customer_id or os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")).strip()
        if not self._dev:
            raise RuntimeError("GOOGLE_ADS_DEVELOPER_TOKEN not configured")

    def _headers(self) -> dict[str, str]:
        h = {
            "Authorization": f"Bearer {self._token}",
            "developer-token": self._dev,
            "Content-Type": "application/json",
        }
        if self._login:
            h["login-customer-id"] = self._login.replace("-", "")
        return h

    def _search(self, customer_id: str, query: str) -> list[dict]:
        cid = str(customer_id).replace("-", "").strip()
        url = _SEARCH.format(customer_id=cid)
        results: list[dict] = []
        page_token: str | None = None
        with httpx.Client(timeout=120.0) as client:
            while True:
                body: dict[str, Any] = {"query": query}
                if page_token:
                    body["pageToken"] = page_token
                resp = client.post(url, headers=self._headers(), json=body)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"Ads search failed: HTTP {resp.status_code} {resp.text[:300]}"
                    )
                data = resp.json()
                results.extend(data.get("results") or [])
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
        return results

    def list_product_metrics(self, ads_customer_id: str) -> list[dict]:
        try:
            rows = self._search(ads_customer_id, _PRODUCT_GAQL)
            parsed = metrics_from_search_rows(rows)
            if parsed:
                return parsed
        except RuntimeError:
            # Soft-degrade to campaign totals (Spec 4B)
            rows = self._search(ads_customer_id, _CAMPAIGN_FALLBACK_GAQL)
            return metrics_from_search_rows(rows)
        rows = self._search(ads_customer_id, _CAMPAIGN_FALLBACK_GAQL)
        return metrics_from_search_rows(rows)
