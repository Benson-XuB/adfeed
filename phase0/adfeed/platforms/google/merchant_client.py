"""Live Merchant Center client (httpx) — reports.search + Content authinfo."""

from __future__ import annotations

import json
from typing import Any

import httpx

_REPORTS_SEARCH = (
    "https://merchantapi.googleapis.com/reports/v1/accounts/{account}/reports:search"
)
_AUTHINFO = "https://shoppingcontent.googleapis.com/content/v2.1/accounts/authinfo"

_DEFAULT_QUERY = (
    "SELECT id, offer_id, title, aggregated_reporting_context_status, item_issues "
    "FROM product_view "
    "WHERE aggregated_reporting_context_status = 'NOT_ELIGIBLE_OR_DISAPPROVED'"
)


def _severity_to_status(severity: dict | None) -> str:
    raw = ""
    if isinstance(severity, dict):
        raw = str(
            severity.get("aggregatedSeverity")
            or severity.get("aggregated_severity")
            or ""
        ).upper()
    mapping = {
        "DISAPPROVED": "disapproved",
        "DEMOTED": "demoted",
        "NOT_IMPACTED": "not_impacted",
        "PENDING": "pending",
    }
    return mapping.get(raw, raw.lower() or "unknown")


def issues_from_report_rows(rows: list[dict]) -> list[dict]:
    """Flatten productView.itemIssues into sync_merchant_issues dicts."""
    out: list[dict] = []
    for row in rows or []:
        pv = row.get("productView") or row.get("product_view") or {}
        offer_id = str(pv.get("offerId") or pv.get("offer_id") or "").strip()
        if not offer_id:
            continue
        issues = pv.get("itemIssues") or pv.get("item_issues") or []
        if not issues:
            # Row matched disapproved filter but no issue detail — keep a stub
            out.append(
                {
                    "offer_id": offer_id,
                    "status": "disapproved",
                    "reason_code": "unknown",
                    "reason_text": str(pv.get("title") or ""),
                    "raw_json": json.dumps(row, ensure_ascii=False),
                }
            )
            continue
        for issue in issues:
            typ = issue.get("type") or {}
            code = str(
                typ.get("code") if isinstance(typ, dict) else typ or ""
            ).strip() or "unknown"
            sev = issue.get("severity") or {}
            desc = str(
                issue.get("description")
                or (issue.get("detail") or {}).get("description")
                or ""
            )
            out.append(
                {
                    "offer_id": offer_id,
                    "status": _severity_to_status(sev if isinstance(sev, dict) else None),
                    "reason_code": code,
                    "reason_text": desc,
                    "raw_json": json.dumps(issue, ensure_ascii=False),
                }
            )
    return out


def merchants_from_authinfo(payload: dict) -> list[dict]:
    ids = payload.get("accountIdentifiers") or payload.get("account_identifiers") or []
    out: list[dict] = []
    for item in ids:
        mid = str(item.get("merchantId") or item.get("merchant_id") or "").strip()
        if not mid:
            continue
        agg = item.get("aggregatorId") or item.get("aggregator_id")
        name = mid if not agg else f"{mid} (MCA {agg})"
        out.append({"merchant_id": mid, "display_name": name})
    return out


class HttpMerchantClient:
    """MerchantIssuesClient + list_merchants via Content authinfo."""

    def __init__(self, access_token: str, *, page_size: int = 250):
        self._token = access_token
        self._page_size = page_size

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    def list_merchants(self) -> list[dict]:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(_AUTHINFO, headers=self._headers())
        if resp.status_code != 200:
            raise RuntimeError(f"authinfo failed: HTTP {resp.status_code} {resp.text[:200]}")
        return merchants_from_authinfo(resp.json())

    def list_product_issues(self, merchant_id: str) -> list[dict]:
        account = str(merchant_id).strip()
        url = _REPORTS_SEARCH.format(account=account)
        page_token: str | None = None
        all_rows: list[dict] = []
        with httpx.Client(timeout=120.0) as client:
            while True:
                body: dict[str, Any] = {
                    "query": _DEFAULT_QUERY,
                    "pageSize": self._page_size,
                }
                if page_token:
                    body["pageToken"] = page_token
                resp = client.post(url, headers=self._headers(), json=body)
                if resp.status_code != 200:
                    raise RuntimeError(
                        f"reports.search failed: HTTP {resp.status_code} {resp.text[:300]}"
                    )
                data = resp.json()
                all_rows.extend(data.get("results") or [])
                page_token = data.get("nextPageToken") or data.get("next_page_token")
                if not page_token:
                    break
        return issues_from_report_rows(all_rows)
