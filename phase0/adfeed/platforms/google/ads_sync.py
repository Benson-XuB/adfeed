"""Ads product-level metrics sync (client injectable). Soft-degrade when empty."""

from __future__ import annotations

from typing import Protocol

from adfeed import store_db


class AdsMetricsClient(Protocol):
    def list_product_metrics(self, ads_customer_id: str) -> list[dict]:
        """Rows: date, offer_id?, campaign_id?, impressions, clicks, cost_micros, conversions."""
        ...


def sync_ads_metrics(
    store_id: str,
    ads_customer_id: str,
    client: AdsMetricsClient,
) -> dict:
    rows = client.list_product_metrics(ads_customer_id) or []
    product_rows = [r for r in rows if str(r.get("offer_id") or "").strip()]
    n = store_db.replace_ads_metrics_daily(store_id, ads_customer_id, rows)
    return {
        "ok": True,
        "written": n,
        "product_level": len(product_rows),
        "degraded": len(product_rows) == 0 and n > 0,
    }
