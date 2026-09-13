"""Google Ads daily report for marketing monitor (live GAQL or demo sample)."""

from __future__ import annotations

import os
import re
from typing import Any

import httpx

# Keep in sync with UI demo cut defaults.
DEFAULT_CUT = "2026-08-17"
ADS_API_VERSION = os.getenv("GOOGLE_ADS_API_VERSION", "v19").strip() or "v19"

# Demo rows shaped like the Doubao monitor (illustrative, not a real account).
SAMPLE_ROWS: list[dict[str, Any]] = [
    {"d": "2026-08-01", "imp": 9200, "clk": 312, "spd": 18.00, "cvn": 7, "cvv": 128.50},
    {"d": "2026-08-02", "imp": 8850, "clk": 296, "spd": 17.80, "cvn": 6, "cvv": 112.40},
    {"d": "2026-08-03", "imp": 9410, "clk": 328, "spd": 18.00, "cvn": 8, "cvv": 139.20},
    {"d": "2026-08-04", "imp": 9060, "clk": 305, "spd": 17.90, "cvn": 7, "cvv": 118.70},
    {"d": "2026-08-05", "imp": 8730, "clk": 289, "spd": 17.60, "cvn": 6, "cvv": 109.80},
    {"d": "2026-08-06", "imp": 9640, "clk": 336, "spd": 18.00, "cvn": 8, "cvv": 141.60},
    {"d": "2026-08-07", "imp": 8980, "clk": 302, "spd": 17.85, "cvn": 7, "cvv": 121.30},
    {"d": "2026-08-08", "imp": 9270, "clk": 318, "spd": 18.00, "cvn": 7, "cvv": 126.80},
    {"d": "2026-08-09", "imp": 8610, "clk": 284, "spd": 17.40, "cvn": 6, "cvv": 105.20},
    {"d": "2026-08-10", "imp": 9520, "clk": 331, "spd": 18.00, "cvn": 8, "cvv": 134.90},
    {"d": "2026-08-11", "imp": 9140, "clk": 309, "spd": 17.95, "cvn": 7, "cvv": 119.60},
    {"d": "2026-08-12", "imp": 8830, "clk": 292, "spd": 17.70, "cvn": 6, "cvv": 111.30},
    {"d": "2026-08-13", "imp": 9390, "clk": 324, "spd": 18.00, "cvn": 8, "cvv": 137.80},
    {"d": "2026-08-14", "imp": 9050, "clk": 301, "spd": 17.85, "cvn": 7, "cvv": 117.20},
    {"d": "2026-08-15", "imp": 9260, "clk": 315, "spd": 18.00, "cvn": 7, "cvv": 124.50},
    {"d": "2026-08-16", "imp": 8890, "clk": 297, "spd": 17.75, "cvn": 6, "cvv": 113.80},
    {"d": "2026-08-17", "imp": 8300, "clk": 272, "spd": 18.00, "cvn": 6, "cvv": 106.40},
    {"d": "2026-08-18", "imp": 7100, "clk": 210, "spd": 18.00, "cvn": 5, "cvv": 88.60},
    {"d": "2026-08-19", "imp": 4650, "clk": 112, "spd": 18.00, "cvn": 4, "cvv": 62.80},
    {"d": "2026-08-20", "imp": 4320, "clk": 104, "spd": 18.00, "cvn": 3, "cvv": 55.20},
    {"d": "2026-08-21", "imp": 4480, "clk": 108, "spd": 18.00, "cvn": 4, "cvv": 58.40},
    {"d": "2026-08-22", "imp": 4190, "clk": 98, "spd": 18.00, "cvn": 3, "cvv": 51.30},
    {"d": "2026-08-23", "imp": 4360, "clk": 103, "spd": 18.00, "cvn": 3, "cvv": 54.70},
    {"d": "2026-08-24", "imp": 4020, "clk": 95, "spd": 18.00, "cvn": 3, "cvv": 49.60},
    {"d": "2026-08-25", "imp": 4270, "clk": 101, "spd": 18.00, "cvn": 3, "cvv": 52.90},
    {"d": "2026-08-26", "imp": 4560, "clk": 110, "spd": 18.00, "cvn": 4, "cvv": 60.10},
    {"d": "2026-08-27", "imp": 4140, "clk": 97, "spd": 18.00, "cvn": 3, "cvv": 50.80},
    {"d": "2026-08-28", "imp": 4390, "clk": 105, "spd": 18.00, "cvn": 4, "cvv": 56.30},
    {"d": "2026-08-29", "imp": 4230, "clk": 99, "spd": 18.00, "cvn": 3, "cvv": 52.10},
    {"d": "2026-08-30", "imp": 4490, "clk": 107, "spd": 18.00, "cvn": 4, "cvv": 57.90},
    {"d": "2026-08-31", "imp": 4080, "clk": 96, "spd": 18.00, "cvn": 3, "cvv": 50.20},
]


def _cid(raw: str) -> str:
    digits = re.sub(r"\D", "", raw or "")
    if len(digits) < 6:
        raise ValueError("Invalid Google Ads customer id")
    return digits


def demo_report(
    *,
    cut: str = DEFAULT_CUT,
    daily_budget: float = 18.0,
    troas_target: float = 200.0,
) -> dict[str, Any]:
    return {
        "ok": True,
        "mode": "demo",
        "notice": (
            "Showing illustrative sample data. Connect Google Ads (OAuth) with a "
            "Test or production account after Cloud project Ads API access is ready."
        ),
        "cut": cut,
        "daily_budget": daily_budget,
        "troas_target": troas_target,
        "currency": "USD",
        "rows": list(SAMPLE_ROWS),
    }


def fetch_daily_rows(
    *,
    access_token: str,
    customer_id: str,
    date_from: str,
    date_to: str,
) -> list[dict[str, Any]]:
    """GAQL daily metrics via Google Ads REST search."""
    from adfeed.public_tools.google_ads_oauth import ads_api_headers

    cid = _cid(customer_id)
    query = f"""
      SELECT
        segments.date,
        metrics.impressions,
        metrics.clicks,
        metrics.cost_micros,
        metrics.conversions,
        metrics.conversions_value
      FROM customer
      WHERE segments.date BETWEEN '{date_from}' AND '{date_to}'
      ORDER BY segments.date
    """
    url = (
        f"https://googleads.googleapis.com/{ADS_API_VERSION}/"
        f"customers/{cid}/googleAds:search"
    )
    headers = ads_api_headers(access_token)

    rows: list[dict[str, Any]] = []
    page_token = ""
    with httpx.Client(timeout=60.0) as client:
        while True:
            body: dict[str, Any] = {"query": query}
            if page_token:
                body["pageToken"] = page_token
            resp = client.post(url, headers=headers, json=body)
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Ads API error HTTP {resp.status_code}: {resp.text[:400]}"
                )
            data = resp.json()
            for result in data.get("results") or []:
                seg = result.get("segments") or {}
                metrics = result.get("metrics") or {}
                cost_micros = float(metrics.get("costMicros") or 0)
                rows.append(
                    {
                        "d": seg.get("date") or "",
                        "imp": int(metrics.get("impressions") or 0),
                        "clk": int(metrics.get("clicks") or 0),
                        "spd": round(cost_micros / 1_000_000.0, 2),
                        "cvn": float(metrics.get("conversions") or 0),
                        "cvv": float(metrics.get("conversionsValue") or 0),
                    }
                )
            page_token = (data.get("nextPageToken") or "").strip()
            if not page_token:
                break
    return rows


def list_accessible_customers(*, access_token: str) -> list[dict[str, str]]:
    from adfeed.public_tools.google_ads_oauth import ads_api_headers

    url = f"https://googleads.googleapis.com/{ADS_API_VERSION}/customers:listAccessibleCustomers"
    headers = ads_api_headers(access_token)
    with httpx.Client(timeout=30.0) as client:
        resp = client.get(url, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(
            f"list customers failed HTTP {resp.status_code}: {resp.text[:300]}"
        )
    names = resp.json().get("resourceNames") or []
    out: list[dict[str, str]] = []
    for name in names:
        # customers/1234567890
        cid = str(name).rsplit("/", 1)[-1]
        out.append({"id": cid, "resource": str(name)})
    return out


def live_report(
    *,
    access_token: str,
    customer_id: str,
    date_from: str,
    date_to: str,
    cut: str,
    daily_budget: float = 18.0,
    troas_target: float = 200.0,
) -> dict[str, Any]:
    rows = fetch_daily_rows(
        access_token=access_token,
        customer_id=customer_id,
        date_from=date_from,
        date_to=date_to,
    )
    return {
        "ok": True,
        "mode": "live",
        "notice": "",
        "customer_id": _cid(customer_id),
        "cut": cut or DEFAULT_CUT,
        "daily_budget": daily_budget,
        "troas_target": troas_target,
        "currency": "USD",
        "date_from": date_from,
        "date_to": date_to,
        "rows": rows,
    }
