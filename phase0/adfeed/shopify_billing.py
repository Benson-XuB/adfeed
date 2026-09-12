"""Shopify Billing — recurring subscriptions + plan → quota mapping."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx

from . import config
from . import store_db

logger = logging.getLogger("adfeed-billing")

# Plan name → monthly quota (env-configurable)
PLAN_QUOTAS = {
    "free": int(os.getenv("ADFEED_QUOTA_FREE", "20")),
    "starter": int(os.getenv("ADFEED_QUOTA_STARTER", "50")),
    "growth": int(os.getenv("ADFEED_QUOTA_GROWTH", "200")),
}

PLAN_PRICES_USD = {
    "starter": float(os.getenv("ADFEED_PRICE_STARTER", "14.99")),
    "growth": float(os.getenv("ADFEED_PRICE_GROWTH", "39.0")),
}

VALID_PAID_PLANS = ("starter", "growth")


def app_handle() -> str:
    """Shopify app handle used in Admin charges URLs (Partner listing slug)."""
    return (os.getenv("SHOPIFY_APP_HANDLE") or "adfeed-ai").strip().strip("/")


def managed_pricing_plans_url(shop_domain: str) -> str:
    """Hosted Shopify App Pricing plan selection (not Billing API create)."""
    raw = (shop_domain or "").strip().replace("https://", "").replace("http://", "")
    store = raw.replace(".myshopify.com", "").split("/")[0]
    if not store:
        raise ValueError("shop_domain required for managed pricing URL")
    return (
        f"https://admin.shopify.com/store/{store}/charges/{app_handle()}/pricing_plans"
    )


def billing_test_charges() -> bool:
    """Production App Store charges must be live (test=false)."""
    return os.getenv("ADFEED_BILLING_TEST", "false").lower() in ("1", "true", "yes")


def normalize_plan_name(name: str) -> str:
    raw = (name or "").strip().lower()
    if not raw:
        return "free"
    # Shopify may send display names like "AdFeed Starter"
    for key in ("growth", "starter", "free"):
        if key in raw:
            return key
    return raw if raw in PLAN_QUOTAS else "free"


def quota_for_plan(plan: str) -> int:
    return PLAN_QUOTAS.get(normalize_plan_name(plan), PLAN_QUOTAS["free"])


def apply_plan_to_store(
    store_id: str,
    plan: str,
    billing_status: str = "active",
    subscription_id: Optional[str] = None,
) -> store_db.Store:
    plan_key = normalize_plan_name(plan)
    kwargs = {
        "plan": plan_key,
        "quota_total": quota_for_plan(plan_key),
        "billing_status": billing_status,
    }
    if subscription_id is not None:
        kwargs["subscription_id"] = subscription_id
    store_db.update_store(store_id, **kwargs)
    return store_db.get_store(store_id)


def apply_plan_handle(
    store_id: str,
    plan_handle: str,
    subscription_id: Optional[str] = None,
) -> store_db.Store:
    """Apply Shopify App Pricing redirect `plan_handle` (free/starter/growth)."""
    plan_key = normalize_plan_name(plan_handle)
    updated = apply_plan_to_store(
        store_id,
        plan=plan_key,
        billing_status="active",
        subscription_id=subscription_id,
    )
    # Managed Pricing often has no Admin activeSubscriptions after cancel.
    # Cache a 30-day paid-through window so uninstall→reinstall keeps access + banner.
    if plan_key in VALID_PAID_PLANS:
        now = _now_utc()
        existing_end = getattr(updated, "subscription_period_end", None)
        if not period_still_open(existing_end):
            started = now.isoformat().replace("+00:00", "Z")
            period_end = (now + timedelta(days=30)).isoformat().replace("+00:00", "Z")
            persist_subscription_period(
                store_id,
                started_at=started,
                period_end=period_end,
                subscription_id=subscription_id,
            )
            updated = store_db.get_store(store_id) or updated
    return updated


def apply_subscription_webhook(payload: dict) -> Optional[store_db.Store]:
    """Handle APP_SUBSCRIPTIONS_UPDATE body → update store plan/quota.

    Payload shapes vary; we accept:
      { "app_subscription": { "admin_graphql_api_id", "name", "status", ... },
        "shop_domain" | "domain": "x.myshopify.com" }
    or nested under `app_subscription`.

    With Shopify App Pricing, webhooks are unreliable / being removed. ACTIVE
    updates still help; CANCELLED must not wipe a plan that was just set via
    plan_handle redirect (common when switching plans).
    """
    sub = payload.get("app_subscription") or payload.get("app_subscriptions") or payload
    if isinstance(sub, list):
        sub = sub[0] if sub else {}

    shop = (
        payload.get("shop_domain")
        or payload.get("domain")
        or payload.get("myshopify_domain")
        or ""
    )
    shop = shop.replace("https://", "").replace("http://", "").strip().lower()
    if shop and not shop.endswith(".myshopify.com"):
        shop = f"{shop}.myshopify.com"

    status_raw = str(sub.get("status") or payload.get("status") or "").upper()
    name = sub.get("name") or sub.get("plan_name") or payload.get("name") or "free"
    sub_id = (
        sub.get("admin_graphql_api_id")
        or sub.get("id")
        or payload.get("admin_graphql_api_id")
    )

    store = store_db.get_store_by_domain(shop) if shop else None
    if not store and sub_id:
        store = store_db.get_store_by_subscription_id(str(sub_id))

    if not store:
        logger.warning("Subscription webhook: store not found for shop=%s", shop)
        return None

    managed = os.getenv("ADFEED_MANAGED_PRICING", "true").lower() in ("1", "true", "yes")

    if status_raw in ("ACTIVE", "ACCEPTED"):
        billing_status = "active"
        plan = normalize_plan_name(name)
    elif status_raw in ("CANCELLED", "DECLINED", "EXPIRED", "FROZEN"):
        if managed:
            # App Pricing: plan_handle redirect is source of truth for upgrades.
            # Cancelling an old Billing API / prior plan must not force Free.
            logger.info(
                "Ignoring %s webhook under managed pricing for shop=%s",
                status_raw,
                shop,
            )
            store_db.update_store(
                store.id,
                billing_status=status_raw.lower(),
                subscription_id=str(sub_id) if sub_id else store.subscription_id,
            )
            return store_db.get_store(store.id)
        billing_status = status_raw.lower()
        plan = "free"
    else:
        billing_status = status_raw.lower() or "none"
        plan = normalize_plan_name(name)

    return apply_plan_to_store(
        store.id,
        plan=plan,
        billing_status=billing_status,
        subscription_id=str(sub_id) if sub_id else store.subscription_id,
    )


def _shopify_admin_shop(store: store_db.Store) -> str:
    return (store.shopify_domain or "").replace(".myshopify.com", "").strip()


def _shopify_graphql_sync(
    store: store_db.Store,
    query: str,
    variables: Optional[dict] = None,
) -> dict:
    """Sync Admin GraphQL call. Raises if store has no access_token."""
    if not store.access_token:
        raise ValueError("store access_token required")
    shop = _shopify_admin_shop(store)
    if not shop:
        raise ValueError("shop_domain required")
    api_version = getattr(config, "SHOPIFY_API_VERSION", "2024-07")
    url = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": store.access_token,
        "Content-Type": "application/json",
    }
    body: dict = {"query": query}
    if variables is not None:
        body["variables"] = variables
    with httpx.Client(timeout=30) as client:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        return resp.json()


_ACTIVE_SUBS_QUERY = """
query {
  currentAppInstallation {
    activeSubscriptions {
      id
      name
      status
      createdAt
      currentPeriodEnd
    }
    allSubscriptions(first: 10, reverse: true, sortKey: CREATED_AT) {
      nodes {
        id
        name
        status
        createdAt
        currentPeriodEnd
      }
    }
  }
}
"""


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    raw = (ts or "").strip()
    if not raw:
        return None
    try:
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def period_still_open(period_end: Optional[str]) -> bool:
    end = _parse_iso(period_end)
    if not end:
        return False
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    return end > _now_utc()


def _node_to_sub(sub: dict) -> dict:
    return {
        "id": sub.get("id") or "",
        "name": sub.get("name") or "",
        "status": str(sub.get("status") or "").upper(),
        "created_at": sub.get("createdAt") or sub.get("created_at") or "",
        "current_period_end": sub.get("currentPeriodEnd") or sub.get("current_period_end") or "",
    }


def _parse_active_subscriptions_payload(data: dict) -> Optional[list[dict]]:
    """Parse GraphQL JSON → active list, or None if response is unusable."""
    if data.get("errors"):
        return None
    install = (data.get("data") or {}).get("currentAppInstallation")
    if install is None:
        return None
    raw = install.get("activeSubscriptions") or []
    out: list[dict] = []
    for sub in raw:
        if isinstance(sub, dict):
            out.append(_node_to_sub(sub))
    return out


def _parse_all_subscriptions_payload(data: dict) -> list[dict]:
    install = (data.get("data") or {}).get("currentAppInstallation") or {}
    conn = install.get("allSubscriptions") or {}
    nodes = conn.get("nodes") or []
    out: list[dict] = []
    for sub in nodes:
        if isinstance(sub, dict):
            out.append(_node_to_sub(sub))
    return out


def estimate_period_end_from_created(created_at: str) -> str:
    """Fallback when Shopify nulls currentPeriodEnd on CANCELLED (common)."""
    start = _parse_iso(created_at)
    if not start:
        return ""
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    end = start + timedelta(days=30)
    return end.isoformat().replace("+00:00", "Z")


def persist_subscription_period(
    store_id: str,
    *,
    started_at: Optional[str] = None,
    period_end: Optional[str] = None,
    subscription_id: Optional[str] = None,
) -> None:
    kwargs: dict = {}
    if started_at is not None:
        kwargs["subscription_started_at"] = started_at or None
    if period_end is not None:
        kwargs["subscription_period_end"] = period_end or None
    if subscription_id is not None:
        kwargs["subscription_id"] = subscription_id or None
    if kwargs:
        store_db.update_store(store_id, **kwargs)


def snapshot_paid_period(store: store_db.Store) -> Optional[dict]:
    """Capture currentPeriodEnd while token still works (before uninstall cancel).

    Shopify marks the charge CANCELLED on uninstall and drops it from
    activeSubscriptions; currentPeriodEnd becomes null. We must cache dates
    locally so reinstall can honor the paid remainder + reviewer banner.
    """
    if not store.access_token:
        return None
    ok, active = load_active_app_subscriptions(store)
    if not ok:
        return None
    primary = None
    for sub in active:
        if sub.get("status") in ("ACTIVE", "ACCEPTED"):
            primary = sub
            break
    if not primary and active:
        primary = active[0]
    if not primary:
        # Fall back to allSubscriptions newest paid-looking row
        try:
            data = _shopify_graphql_sync(store, _ACTIVE_SUBS_QUERY)
            for sub in _parse_all_subscriptions_payload(data):
                if normalize_plan_name(sub.get("name") or "") in VALID_PAID_PLANS:
                    primary = sub
                    break
        except Exception as exc:
            logger.warning("snapshot allSubscriptions failed: %s", exc)
            return None
    if not primary:
        return None

    started = primary.get("created_at") or ""
    period_end = primary.get("current_period_end") or ""
    if not period_end and started:
        period_end = estimate_period_end_from_created(started)
    persist_subscription_period(
        store.id,
        started_at=started,
        period_end=period_end,
        subscription_id=primary.get("id") or store.subscription_id,
    )
    plan = normalize_plan_name(primary.get("name") or store.plan or "free")
    if plan in VALID_PAID_PLANS and store.plan != plan:
        apply_plan_to_store(
            store.id,
            plan=plan,
            billing_status=store.billing_status or "active",
            subscription_id=primary.get("id") or store.subscription_id,
        )
    return {
        "id": primary.get("id") or "",
        "name": primary.get("name") or plan,
        "status": primary.get("status") or "ACTIVE",
        "created_at": started,
        "current_period_end": period_end,
    }


def grace_subscription_payload(store: store_db.Store) -> Optional[dict]:
    """Paid-through entitlement when Shopify already CANCELLED the charge."""
    plan = normalize_plan_name(store.plan or "free")
    period_end = store.subscription_period_end or ""
    started = store.subscription_started_at or ""
    if plan not in VALID_PAID_PLANS:
        return None
    if not period_still_open(period_end):
        return None
    name = f"AdFeed {plan.title()}"
    return active_subscription_payload(
        {
            "id": store.subscription_id or "",
            "name": name,
            "status": "CANCELLED",
            "created_at": started,
            "current_period_end": period_end,
        },
        persists_after_reinstall=True,
    )


def load_active_app_subscriptions(
    store: store_db.Store,
) -> tuple[bool, list[dict]]:
    """Return (ok, subscriptions). ok=False → do not mutate local billing."""
    if not store.access_token:
        return False, []
    try:
        data = _shopify_graphql_sync(store, _ACTIVE_SUBS_QUERY)
    except Exception as exc:
        logger.warning(
            "load_active_app_subscriptions failed for %s: %s",
            store.shopify_domain,
            exc,
        )
        return False, []
    parsed = _parse_active_subscriptions_payload(data)
    if parsed is None:
        logger.warning(
            "load_active_app_subscriptions unusable payload for %s: %s",
            store.shopify_domain,
            data.get("errors") or "missing currentAppInstallation",
        )
        return False, []
    # Stash allSubscriptions on the store object for this request (optional recovery)
    try:
        store._all_subscriptions_cache = _parse_all_subscriptions_payload(data)  # type: ignore[attr-defined]
    except Exception:
        pass
    return True, parsed


def fetch_active_app_subscriptions(store: store_db.Store) -> list[dict]:
    """Query Shopify for currentAppInstallation.activeSubscriptions.

    Returns list of dicts: id, name, status, created_at, current_period_end.
    Empty list when no token, no active subscriptions, or GraphQL errors.
    """
    _ok, subs = load_active_app_subscriptions(store)
    return subs


def cancel_app_subscriptions(store: store_db.Store) -> dict:
    """Best-effort appSubscriptionCancel before uninstall clears the token.

    Managed Pricing may return userErrors; callers must still clear local state
    and rely on cached period_end + reinstall banner when Shopify keeps the
    paid remainder (activeSubscriptions will be empty after CANCELLED).
    """
    result: dict = {"attempted": 0, "cancelled_ids": [], "errors": []}
    if not store.access_token:
        return result

    ids: list[str] = []
    if store.subscription_id:
        ids.append(str(store.subscription_id))
    for sub in fetch_active_app_subscriptions(store):
        sid = sub.get("id") or ""
        if sid and sid not in ids:
            ids.append(sid)

    mutation = """
    mutation AppSubscriptionCancel($id: ID!) {
      appSubscriptionCancel(id: $id) {
        appSubscription { id status }
        userErrors { field message }
      }
    }
    """
    for sub_id in ids:
        result["attempted"] += 1
        try:
            data = _shopify_graphql_sync(store, mutation, {"id": sub_id})
        except Exception as exc:
            msg = f"{sub_id}: {exc}"
            result["errors"].append(msg)
            logger.warning("appSubscriptionCancel failed: %s", msg)
            continue
        payload = (data.get("data") or {}).get("appSubscriptionCancel") or {}
        errors = payload.get("userErrors") or []
        if errors:
            result["errors"].append(f"{sub_id}: {errors}")
            logger.info(
                "appSubscriptionCancel userErrors for %s: %s",
                store.shopify_domain,
                errors,
            )
            continue
        cancelled = (payload.get("appSubscription") or {}).get("id") or sub_id
        result["cancelled_ids"].append(cancelled)
    return result


def active_subscription_payload(
    sub: dict,
    *,
    persists_after_reinstall: bool = True,
) -> dict:
    return {
        "id": sub.get("id") or "",
        "name": sub.get("name") or "",
        "status": str(sub.get("status") or "").upper(),
        "created_at": sub.get("created_at") or "",
        "current_period_end": sub.get("current_period_end") or "",
        "persists_after_reinstall": bool(persists_after_reinstall),
    }


def _recover_grace_from_all_subscriptions(
    store: store_db.Store,
) -> Optional[tuple[store_db.Store, dict]]:
    """After wipe-to-free, recover paid-through from CANCELLED allSubscriptions."""
    nodes = getattr(store, "_all_subscriptions_cache", None)
    if nodes is None and store.access_token:
        try:
            data = _shopify_graphql_sync(store, _ACTIVE_SUBS_QUERY)
            nodes = _parse_all_subscriptions_payload(data)
        except Exception:
            nodes = []
    for sub in nodes or []:
        plan = normalize_plan_name(sub.get("name") or "")
        if plan not in VALID_PAID_PLANS:
            continue
        started = sub.get("created_at") or ""
        period_end = sub.get("current_period_end") or ""
        if not period_end and started:
            period_end = estimate_period_end_from_created(started)
        if not period_still_open(period_end):
            continue
        persist_subscription_period(
            store.id,
            started_at=started,
            period_end=period_end,
            subscription_id=sub.get("id") or None,
        )
        updated = apply_plan_to_store(
            store.id,
            plan=plan,
            billing_status="cancelled",
            subscription_id=sub.get("id") or None,
        )
        return updated, active_subscription_payload(
            {
                "id": sub.get("id") or "",
                "name": sub.get("name") or f"AdFeed {plan.title()}",
                "status": "CANCELLED",
                "created_at": started,
                "current_period_end": period_end,
            },
            persists_after_reinstall=True,
        )
    return None


def sync_billing_from_shopify(store: store_db.Store) -> tuple[store_db.Store, Optional[dict]]:
    """Align local plan with Shopify; honor paid-through after CANCELLED uninstall.

    Shopify docs: uninstall cancels the subscription, but the merchant may
    reinstall and use the app until the remainder of the billing period.
    activeSubscriptions is empty once CANCELLED — do not treat that as free
    while subscription_period_end is still in the future.
    """
    grace = grace_subscription_payload(store)
    if not store.access_token:
        return store, grace

    ok, subs = load_active_app_subscriptions(store)
    if not ok:
        return store, grace

    active = [s for s in subs if s.get("status") in ("ACTIVE", "ACCEPTED")]

    if active:
        primary = active[0]
        plan_key = normalize_plan_name(primary.get("name") or "free")
        started = primary.get("created_at") or ""
        period_end = primary.get("current_period_end") or ""
        if not period_end and started:
            period_end = estimate_period_end_from_created(started)
        persist_subscription_period(
            store.id,
            started_at=started,
            period_end=period_end,
            subscription_id=primary.get("id") or None,
        )
        updated = apply_plan_to_store(
            store.id,
            plan=plan_key,
            billing_status="active",
            subscription_id=primary.get("id") or None,
        )
        updated = store_db.get_store(store.id) or updated
        payload = active_subscription_payload(
            {
                "id": primary.get("id") or "",
                "name": primary.get("name") or "",
                "status": primary.get("status") or "ACTIVE",
                "created_at": started,
                "current_period_end": period_end,
            },
            persists_after_reinstall=plan_key in VALID_PAID_PLANS,
        )
        return updated, payload

    # No ACTIVE — keep paid grace if we still have period_end locally
    refreshed = store_db.get_store(store.id) or store
    grace = grace_subscription_payload(refreshed)
    if grace:
        plan = normalize_plan_name(refreshed.plan)
        if plan in VALID_PAID_PLANS:
            # Keep paid quota in sync (uninstall must not leave free quota on paid plan)
            if int(refreshed.quota_total or 0) != quota_for_plan(plan):
                refreshed = apply_plan_to_store(
                    refreshed.id,
                    plan=plan,
                    billing_status=refreshed.billing_status or "cancelled",
                    subscription_id=refreshed.subscription_id,
                )
                # re-apply period fields wiped? apply_plan_to_store doesn't touch period
            return refreshed, grace

    recovered = _recover_grace_from_all_subscriptions(store)
    if recovered:
        return recovered

    # Truly no paid remainder
    updated = apply_plan_to_store(
        store.id,
        plan="free",
        billing_status="none",
        subscription_id="",
    )
    persist_subscription_period(store.id, started_at="", period_end="")
    return updated, None


def build_billing_status_response(store: store_db.Store) -> dict:
    """Billing status JSON including optional active_subscription for App banner."""
    synced, active_sub = sync_billing_from_shopify(store)
    pricing_url = ""
    try:
        pricing_url = managed_pricing_plans_url(synced.shopify_domain)
    except ValueError:
        pricing_url = ""
    out = {
        "store_id": synced.id,
        "shop_domain": synced.shopify_domain,
        "shop_name": synced.shop_name,
        "plan": synced.plan,
        "billing_status": synced.billing_status,
        "quota_total": synced.quota_total,
        "quota_used": synced.quota_used,
        "quota_remaining": synced.quota_remaining,
        "subscription_id": synced.subscription_id,
        "subscription_started_at": synced.subscription_started_at,
        "subscription_period_end": synced.subscription_period_end,
        "pricing_plans_url": pricing_url,
        "managed_pricing": True,
        "active_subscription": active_sub,
    }
    return out


async def create_app_subscription(
    store: store_db.Store,
    plan: str,
    return_url: str,
    test: Optional[bool] = None,
) -> dict:
    """Create Shopify recurring application charge via GraphQL.

    Returns: {confirmation_url, subscription_id, plan, quota_total}
    When store has no access_token (dev/tests), returns a mock confirmation URL.
    """
    plan_key = normalize_plan_name(plan)
    if plan_key not in VALID_PAID_PLANS:
        raise ValueError(f"Unsupported plan '{plan}'. Use starter or growth.")
    if test is None:
        test = billing_test_charges()

    price = PLAN_PRICES_USD[plan_key]
    quota = quota_for_plan(plan_key)
    name = f"AdFeed {plan_key.title()}"

    if not store.access_token:
        # Dev / unit-test path without live Shopify token
        fake_id = f"gid://shopify/AppSubscription/mock-{plan_key}"
        store_db.update_store(store.id, subscription_id=fake_id, plan=plan_key)
        conf = f"{return_url}?charge_id=mock-{plan_key}&store_id={store.id}"
        return {
            "confirmation_url": conf,
            "subscription_id": fake_id,
            "plan": plan_key,
            "quota_total": quota,
            "mock": True,
        }

    shop = store.shopify_domain.replace(".myshopify.com", "").strip()
    mutation = """
    mutation AppSubscriptionCreate($name: String!, $returnUrl: URL!, $test: Boolean!, $lineItems: [AppSubscriptionLineItemInput!]!) {
      appSubscriptionCreate(name: $name, returnUrl: $returnUrl, test: $test, lineItems: $lineItems) {
        appSubscription { id status }
        confirmationUrl
        userErrors { field message }
      }
    }
    """
    variables = {
        "name": name,
        "returnUrl": return_url,
        "test": test,
        "lineItems": [
            {
                "plan": {
                    "appRecurringPricingDetails": {
                        "price": {"amount": price, "currencyCode": "USD"},
                        "interval": "EVERY_30_DAYS",
                    }
                }
            }
        ],
    }

    api_version = getattr(config, "SHOPIFY_API_VERSION", "2024-07")
    url = f"https://{shop}.myshopify.com/admin/api/{api_version}/graphql.json"
    headers = {
        "X-Shopify-Access-Token": store.access_token,
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(url, headers=headers, json={"query": mutation, "variables": variables})
        resp.raise_for_status()
        data = resp.json()

    payload = (data.get("data") or {}).get("appSubscriptionCreate") or {}
    errors = payload.get("userErrors") or []
    if errors:
        raise RuntimeError(f"Shopify billing error: {errors}")

    conf_url = payload.get("confirmationUrl")
    sub = payload.get("appSubscription") or {}
    sub_id = sub.get("id")
    if sub_id:
        store_db.update_store(store.id, subscription_id=sub_id, plan=plan_key)

    return {
        "confirmation_url": conf_url,
        "subscription_id": sub_id,
        "plan": plan_key,
        "quota_total": quota,
        "mock": False,
    }
