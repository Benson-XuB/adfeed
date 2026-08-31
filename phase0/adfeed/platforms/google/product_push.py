"""Push canonical feed rows to Merchant API productInputs (mockable).

Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional, Protocol, Sequence

import httpx

from adfeed import store_db
from adfeed.platforms.google.product_mapper import map_row_to_product_input

_INSERT_URL = (
    "https://merchantapi.googleapis.com/products/v1/accounts/{account}/productInputs:insert"
)


class PushItemError(Exception):
    """One product insert failed; push loop records fail and continues."""

    def __init__(self, code: str, message: str):
        self.code = str(code or "ERROR")
        self.message = str(message or "")
        super().__init__(f"{self.code}: {self.message}")


class ProductPushClient(Protocol):
    def insert_product_input(
        self,
        *,
        merchant_id: str,
        data_source: str,
        product_input: Mapping[str, Any],
    ) -> dict:
        ...


class LiveProductPushClient:
    """HTTP client for Merchant products.productInputs.insert."""

    def __init__(self, access_token: str, *, timeout: float = 60.0):
        self._token = access_token
        self._timeout = timeout

    def insert_product_input(
        self,
        *,
        merchant_id: str,
        data_source: str,
        product_input: Mapping[str, Any],
    ) -> dict:
        account = str(merchant_id).strip()
        url = _INSERT_URL.format(account=account)
        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._timeout) as client:
            resp = client.post(
                url,
                headers=headers,
                params={"dataSource": data_source},
                json=dict(product_input),
            )
        if resp.status_code >= 400:
            code, message = _error_from_response(resp)
            raise PushItemError(code, message)
        try:
            return resp.json()
        except Exception:
            return {"raw": resp.text}


def _error_from_response(resp: httpx.Response) -> tuple[str, str]:
    code = f"HTTP_{resp.status_code}"
    message = (resp.text or "")[:500]
    try:
        data = resp.json()
    except Exception:
        return code, message
    err = data.get("error") if isinstance(data, dict) else None
    if isinstance(err, dict):
        code = str(err.get("status") or err.get("code") or code)
        message = str(err.get("message") or message)
    return code, message


def _row_sku(row: Mapping[str, Any]) -> str:
    for key in ("SKU", "sku"):
        if key not in row:
            continue
        val = row.get(key)
        if val is None:
            continue
        text = str(val).strip().replace(" ", "-")
        if text.lower() in ("", "nan", "none"):
            continue
        return text
    return ""


def push_canonical_rows(
    store_id: str,
    merchant_id: str,
    data_source: str,
    rows: Sequence[Mapping[str, Any]],
    *,
    client: Optional[ProductPushClient] = None,
    access_token: Optional[str] = None,
    channel: str = "online",
    content_language: str = "en",
    feed_label: str = "US",
) -> dict:
    """Map rows → productInputs.insert; record ok/fail on google_push_* tables.

    Skips rows with empty SKU (never invent offerId). Sequential for v1.
    """
    if client is None:
        if not access_token:
            raise ValueError("access_token or client is required")
        client = LiveProductPushClient(access_token)

    run = store_db.create_push_run(store_id, merchant_id)
    run_id = run["id"]
    ok_count = 0
    fail_count = 0

    for row in rows:
        sku = _row_sku(row)
        if not sku:
            continue
        product_input = map_row_to_product_input(
            row,
            channel=channel,
            content_language=content_language,
            feed_label=feed_label,
        )
        # Mapper may still yield empty offerId if only whitespace survived — skip.
        if not str(product_input.get("offerId") or "").strip():
            continue
        try:
            result = client.insert_product_input(
                merchant_id=merchant_id,
                data_source=data_source,
                product_input=product_input,
            )
            store_db.add_push_item(
                run_id,
                offer_id=product_input["offerId"],
                status="ok",
                raw_json=json.dumps(result, ensure_ascii=False)
                if result is not None
                else None,
            )
            ok_count += 1
        except PushItemError as exc:
            store_db.add_push_item(
                run_id,
                offer_id=product_input["offerId"],
                status="fail",
                error_code=exc.code,
                error_text=exc.message,
            )
            fail_count += 1

    finished = store_db.finish_push_run(
        run_id,
        ok_count=ok_count,
        fail_count=fail_count,
        status="done",
    )
    return {
        "id": finished["id"],
        "ok_count": finished["ok_count"],
        "fail_count": finished["fail_count"],
        "status": finished["status"],
        "merchant_id": finished.get("merchant_id"),
        "store_id": finished.get("store_id"),
    }
