"""Merchant reports helpers for public Google issues tool."""

from __future__ import annotations

from typing import Any

import httpx

from adfeed.public_tools.issue_copy import classify_issues, enrich_issue

_REPORTS_SEARCH = (
    "https://merchantapi.googleapis.com/reports/v1/accounts/{account}/reports:search"
)
_ACCOUNTS_LIST = "https://merchantapi.googleapis.com/accounts/v1/accounts"

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


def _issue_texts(issue: dict) -> tuple[str, str]:
    """Return (code, best human text Google gave us)."""
    typ = issue.get("type") or {}
    code = str(typ.get("code") if isinstance(typ, dict) else typ or "").strip() or "unknown"
    candidates: list[str] = []
    for key in ("description", "detail", "documentation"):
        val = issue.get(key)
        if isinstance(val, dict):
            for sub in ("description", "detail", "title", "content"):
                t = str(val.get(sub) or "").strip()
                if t:
                    candidates.append(t)
        else:
            t = str(val or "").strip()
            if t:
                candidates.append(t)
    sev = issue.get("severity") or {}
    if isinstance(sev, dict):
        for sub in ("description", "details", "detail"):
            t = str(sev.get(sub) or "").strip()
            if t:
                candidates.append(t)
    # Some payloads nest resolution hints
    res = issue.get("resolution") or {}
    if isinstance(res, dict):
        t = str(res.get("description") or res.get("detail") or "").strip()
        if t:
            candidates.append(t)
    text = candidates[0] if candidates else ""
    return code, text


def issues_from_report_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows or []:
        pv = row.get("productView") or row.get("product_view") or {}
        offer_id = str(pv.get("offerId") or pv.get("offer_id") or "").strip()
        title = str(pv.get("title") or "").strip()
        if not offer_id:
            continue
        issues = pv.get("itemIssues") or pv.get("item_issues") or []
        if not issues:
            base = {
                "offer_id": offer_id,
                "title": title,
                "status": "disapproved",
                "reason_code": "unknown",
                "reason_text": "",
                "google_reason": "",
            }
            base.update(enrich_issue("unknown", ""))
            out.append(base)
            continue
        for issue in issues:
            code, desc = _issue_texts(issue if isinstance(issue, dict) else {})
            sev = issue.get("severity") if isinstance(issue, dict) else {}
            row_out = {
                "offer_id": offer_id,
                "title": title,
                "status": _severity_to_status(sev if isinstance(sev, dict) else None),
                "reason_code": code,
                "reason_text": desc,
                "google_reason": desc,
            }
            row_out.update(enrich_issue(code, desc))
            out.append(row_out)
    return out


def fetch_disapproved_issues(
    access_token: str,
    merchant_id: str,
    *,
    limit: int = 50,
) -> dict[str, Any]:
    account = str(merchant_id).strip()
    url = _REPORTS_SEARCH.format(account=account)
    headers = {"Authorization": f"Bearer {access_token}"}
    page_size = min(max(limit, 1), 250)
    body = {"query": _DEFAULT_QUERY, "pageSize": page_size}
    with httpx.Client(timeout=120.0) as client:
        resp = client.post(url, headers=headers, json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"reports.search failed: HTTP {resp.status_code} {resp.text[:300]}")
    payload = resp.json()
    rows = payload.get("results") or []
    issues = issues_from_report_rows(rows)[:limit]
    diagnosis = classify_issues(issues)
    return {
        "ok": True,
        "merchant_id": account,
        "issue_count": len(issues),
        "diagnosis": diagnosis,
        # Intentionally omit product rows from the public diagnostic contract.
        "adfeed_helps": [
            "Clean noisy supplier titles and variant attributes into a Shopping-ready feed",
            "Confirm brand and use compliant no-GTIN handling (never fake barcodes)",
            "Publish a stable synced feed URL after catalog fixes",
        ],
        "adfeed_cannot": [
            "Clear account-level policy suspensions — only Merchant Center can do that",
            "Change bids or run Google Ads in this free tool",
        ],
    }


def demo_diagnosis(kind: str) -> dict[str, Any]:
    """Synthetic ACCOUNT / FEED / MIXED payloads for local UX acceptance."""
    key = (kind or "").strip().lower()
    if key == "account":
        issues = [
            {
                "offer_id": f"A-{i}",
                "title": "Demo",
                "reason_code": "policy_enforcement_account_disapproval",
            }
            for i in range(12)
        ]
    elif key == "feed":
        codes = [
            "title",
            "title",
            "title",
            "brand",
            "brand",
            "gtin",
            "gtin",
            "color",
            "image_link",
            "missing_item_attribute",
        ]
        issues = [
            {"offer_id": f"F-{i}", "title": "Demo", "reason_code": code}
            for i, code in enumerate(codes)
        ]
    elif key == "mixed":
        issues = [
            {
                "offer_id": f"A-{i}",
                "title": "Demo",
                "reason_code": "policy_enforcement_account_disapproval",
            }
            for i in range(4)
        ] + [
            {"offer_id": f"F-{i}", "title": "Demo", "reason_code": code}
            for i, code in enumerate(["title", "title", "brand", "gtin"])
        ]
    elif key == "none":
        issues = []
    else:
        raise ValueError("demo kind must be account|feed|mixed|none")

    diagnosis = classify_issues(issues)
    return {
        "ok": True,
        "demo": True,
        "merchant_id": "demo",
        "issue_count": len(issues),
        "diagnosis": diagnosis,
        "adfeed_helps": [
            "Clean noisy supplier titles and variant attributes into a Shopping-ready feed",
            "Confirm brand and use compliant no-GTIN handling (never fake barcodes)",
            "Publish a stable synced feed URL after catalog fixes",
        ],
        "adfeed_cannot": [
            "Clear account-level policy suspensions — only Merchant Center can do that",
            "Change bids or run Google Ads in this free tool",
        ],
    }


def list_merchant_accounts(access_token: str) -> list[dict[str, str]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=60.0) as client:
        resp = client.get(_ACCOUNTS_LIST, headers=headers)
    if resp.status_code != 200:
        raise RuntimeError(f"accounts.list failed: HTTP {resp.status_code} {resp.text[:300]}")
    data = resp.json()
    accounts = data.get("accounts") or []
    out: list[dict[str, str]] = []
    for acc in accounts:
        name = str(acc.get("name") or "")
        # name format: accounts/123
        mid = name.split("/")[-1] if name else str(acc.get("accountId") or "")
        if not mid:
            continue
        label = str(acc.get("accountName") or mid)
        out.append({"merchant_id": mid, "display_name": label})
    return out
