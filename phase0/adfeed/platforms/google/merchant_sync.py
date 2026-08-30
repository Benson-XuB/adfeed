"""Sync Merchant Center product issues into store_db (client injectable for tests)."""

from __future__ import annotations

from typing import Protocol

from adfeed import store_db
from adfeed.platforms.google.issue_actions import suggest_action
from adfeed.platforms.google.offer_match import match_offer_to_sku


class MerchantIssuesClient(Protocol):
    def list_product_issues(self, merchant_id: str) -> list[dict]:
        """Return dicts with offer_id, status, reason_code, reason_text; optional raw."""
        ...


def sync_merchant_issues(
    store_id: str,
    merchant_id: str,
    client: MerchantIssuesClient,
    sku_set: set[str] | None = None,
) -> dict:
    skus = sku_set if sku_set is not None else store_db.list_store_skus(store_id)
    raw_issues = client.list_product_issues(merchant_id) or []
    rows: list[dict] = []
    matched = 0
    unmatched = 0
    for it in raw_issues:
        oid = str(it.get("offer_id") or "").strip()
        if not oid:
            continue
        internal = match_offer_to_sku(oid, skus)
        if internal:
            matched += 1
        else:
            unmatched += 1
        status = str(it.get("status") or "").strip().lower() or "unknown"
        reason_code = str(it.get("reason_code") or "")
        rows.append(
            {
                "offer_id": oid,
                "product_id_internal": internal,
                "status": status,
                "reason_code": reason_code,
                "reason_text": str(it.get("reason_text") or ""),
                "raw_json": it.get("raw_json"),
                "suggested_action": suggest_action(reason_code)["action"],
            }
        )
    n = store_db.replace_gmc_product_issues(store_id, merchant_id, rows)
    return {
        "ok": True,
        "written": n,
        "matched": matched,
        "unmatched": unmatched,
    }
