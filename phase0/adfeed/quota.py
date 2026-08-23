"""Quota: SKU × platform × language estimate + debit helpers."""

from __future__ import annotations

from typing import Iterable, Sequence

from fastapi import HTTPException

from . import store_db


def estimate_cost(
    sku_count: int,
    platforms: Sequence[str] | Iterable[str],
    languages: Sequence[str] | Iterable[str],
) -> int:
    """Return units = SKU × platforms × languages."""
    plats = [p for p in platforms if p]
    langs = [l for l in languages if l]
    if sku_count < 0:
        sku_count = 0
    return int(sku_count) * len(plats) * len(langs)


def assert_quota_available(store: store_db.Store, cost: int) -> None:
    """Raise HTTP 402 when estimate exceeds remaining quota (block, no truncate)."""
    remaining = store.quota_remaining
    if cost > remaining:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "insufficient_quota",
                "message": (
                    f"Need {cost} quota units; {remaining} remaining. "
                    "Upgrade your plan to generate more."
                ),
                "estimate": cost,
                "quota_remaining": remaining,
                "quota_total": store.quota_total,
                "quota_used": store.quota_used,
                "plan": store.plan,
            },
        )


def debit_quota(
    store_id: str,
    platform: str,
    language: str,
    job_id: str | None = None,
    sku: str | None = None,
) -> str:
    """Debit one unit after a successful product_assets write."""
    return store_db.record_usage(
        store_id=store_id,
        platform=platform,
        language=language,
        job_id=job_id,
        sku=sku,
    )


def debit_for_assets(
    store_id: str,
    units: Sequence[tuple[str, str, str]],
    job_id: str | None = None,
) -> int:
    """Debit for each (sku, platform, language) success tuple. Returns count."""
    n = 0
    for sku, platform, language in units:
        debit_quota(store_id, platform, language, job_id=job_id, sku=sku)
        n += 1
    return n
