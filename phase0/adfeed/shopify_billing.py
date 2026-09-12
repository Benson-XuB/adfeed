"""Shopify Billing — recurring subscriptions + plan → quota mapping."""

from __future__ import annotations

import logging
import os
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
    return apply_plan_to_store(
        store_id,
        plan=normalize_plan_name(plan_handle),
        billing_status="active",
        subscription_id=subscription_id,
    )


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


def _parse_active_subscriptions_payload(data: dict) -> Optional[list[dict]]:
    """Parse GraphQL JSON → list, or None if response is unusable."""
    if data.get("errors"):
        return None
    install = (data.get("data") or {}).get("currentAppInstallation")
    if install is None:
        return None
    raw = install.get("activeSubscriptions") or []
    out: list[dict] = []
    for sub in raw:
        if not isinstance(sub, dict):
            continue
        out.append(
            {
                "id": sub.get("id") or "",
                "name": sub.get("name") or "",
                "status": str(sub.get("status") or "").upper(),
                "created_at": sub.get("createdAt") or "",
                "current_period_end": sub.get("currentPeriodEnd") or "",
            }
        )
    return out


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
  }
}
"""


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
    and rely on reinstall banner when Shopify keeps the charge until period end.
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


def sync_billing_from_shopify(store: store_db.Store) -> tuple[store_db.Store, Optional[dict]]:
    """Align local plan with Shopify activeSubscriptions; return banner payload.

    - ACTIVE paid sub → apply plan + return active_subscription (for UI banner).
    - No active subs (successful empty query with token) → downgrade to free.
    - Fetch failure / no token → leave local plan unchanged, no banner payload.
    """
    if not store.access_token:
        return store, None

    had_prior_cancelled = (store.billing_status or "").lower() in (
        "cancelled",
        "canceled",
        "expired",
    ) or (store.status or "").lower() == "inactive"

    ok, subs = load_active_app_subscriptions(store)
    if not ok:
        return store, None

    active = [s for s in subs if s.get("status") in ("ACTIVE", "ACCEPTED")]

    if not active:
        updated = apply_plan_to_store(
            store.id,
            plan="free",
            billing_status="none",
            subscription_id="",
        )
        return updated, None

    primary = active[0]
    plan_key = normalize_plan_name(primary.get("name") or "free")
    updated = apply_plan_to_store(
        store.id,
        plan=plan_key,
        billing_status="active",
        subscription_id=primary.get("id") or None,
    )
    # Reviewer: leftover period after reinstall must show plan + start + end.
    persists = had_prior_cancelled or plan_key in VALID_PAID_PLANS
    payload = active_subscription_payload(primary, persists_after_reinstall=persists)
    return updated, payload


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
