"""List Merchant accounts for App Google connection."""

from __future__ import annotations

import httpx

_ACCOUNTS_LIST = "https://merchantapi.googleapis.com/accounts/v1/accounts"


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
        mid = name.split("/")[-1] if name else str(acc.get("accountId") or "")
        if not mid:
            continue
        label = str(acc.get("accountName") or mid)
        out.append({"merchant_id": mid, "display_name": label})
    return out
