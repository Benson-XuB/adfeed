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


def normalize_window_days(window_days: int | None) -> int:
    """Only 7 or 30 are supported; anything else → 7."""
    try:
        wd = int(window_days) if window_days is not None else 7
    except (TypeError, ValueError):
        return 7
    return 30 if wd == 30 else 7


def _during_clause(window_days: int) -> str:
    wd = normalize_window_days(window_days)
    return f"LAST_{wd}_DAYS"


def build_product_gaql(window_days: int = 7) -> str:
    during = _during_clause(window_days)
    return f"""
SELECT
  segments.date,
  segments.product_item_id,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM shopping_performance_view
WHERE segments.date DURING {during}
""".strip()


def build_campaign_fallback_gaql(window_days: int = 7) -> str:
    during = _during_clause(window_days)
    return f"""
SELECT
  segments.date,
  campaign.id,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM campaign
WHERE segments.date DURING {during}
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

    def list_product_metrics(
        self, ads_customer_id: str, window_days: int = 7
    ) -> list[dict]:
        wd = normalize_window_days(window_days)
        product_q = build_product_gaql(wd)
        campaign_q = build_campaign_fallback_gaql(wd)
        try:
            rows = self._search(ads_customer_id, product_q)
            parsed = metrics_from_search_rows(rows)
            if parsed:
                return parsed
        except RuntimeError:
            # Soft-degrade to campaign totals (Spec 4B)
            rows = self._search(ads_customer_id, campaign_q)
            return metrics_from_search_rows(rows)
        rows = self._search(ads_customer_id, campaign_q)
        return metrics_from_search_rows(rows)
