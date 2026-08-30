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
    "free": int(os.getenv("ADFEED_QUOTA_FREE", "3")),
    "starter": int(os.getenv("ADFEED_QUOTA_STARTER", "50")),
    "growth": int(os.getenv("ADFEED_QUOTA_GROWTH", "200")),
}

PLAN_PRICES_USD = {
    "starter": float(os.getenv("ADFEED_PRICE_STARTER", "14.99")),
    "growth": float(os.getenv("ADFEED_PRICE_GROWTH", "39.0")),
}

VALID_PAID_PLANS = ("starter", "growth")


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


def apply_subscription_webhook(payload: dict) -> Optional[store_db.Store]:
    """Handle APP_SUBSCRIPTIONS_UPDATE body → update store plan/quota.

    Payload shapes vary; we accept:
      { "app_subscription": { "admin_graphql_api_id", "name", "status", ... },
        "shop_domain" | "domain": "x.myshopify.com" }
    or nested under `app_subscription`.
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

    if status_raw in ("ACTIVE", "ACCEPTED"):
        billing_status = "active"
        plan = normalize_plan_name(name)
    elif status_raw in ("CANCELLED", "DECLINED", "EXPIRED", "FROZEN"):
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
