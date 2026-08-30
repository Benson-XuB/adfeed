"""Sync Meta catalog product issues into store_db."""

from __future__ import annotations

from typing import Protocol

from adfeed import store_db
from adfeed.platforms.common.issue_actions import suggest_action
from adfeed.platforms.common.offer_match import match_offer_to_sku


class MetaIssuesClient(Protocol):
    def list_product_issues(self, catalog_id: str) -> list[dict]:
        ...


def sync_meta_issues(
    store_id: str,
    catalog_id: str,
    client: MetaIssuesClient,
    sku_set: set[str] | None = None,
) -> dict:
    skus = sku_set if sku_set is not None else store_db.list_store_skus(store_id)
    raw = client.list_product_issues(catalog_id) or []
    rows: list[dict] = []
    matched = unmatched = 0
    for it in raw:
        oid = str(it.get("offer_id") or "").strip()
        if not oid:
            continue
        internal = match_offer_to_sku(oid, skus)
        if internal:
            matched += 1
        else:
            unmatched += 1
        reason_code = str(it.get("reason_code") or "")
        rows.append(
            {
                "offer_id": oid,
                "product_id_internal": internal,
                "status": str(it.get("status") or "").strip().lower() or "unknown",
                "reason_code": reason_code,
                "reason_text": str(it.get("reason_text") or ""),
                "raw_json": it.get("raw_json"),
                "suggested_action": suggest_action(reason_code)["action"],
            }
        )
    n = store_db.replace_meta_product_issues(store_id, catalog_id, rows)
    return {"ok": True, "written": n, "matched": matched, "unmatched": unmatched}
