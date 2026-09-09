# Shopify App Pricing（方案 B）— 2026-09-09

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**Status:** Implemented in code (needs full App deploy + Partner plan names aligned)

## Problem

Reviewer error:

`Cannot use the Billing API (to create charges) when on Shopify App Pricing.`

## Decision

Keep **Shopify App Pricing**. Stop calling `appSubscriptionCreate`.

- Plans UI → redirect `…/charges/{SHOPIFY_APP_HANDLE}/pricing_plans` (`target=_top`)
- `POST /api/app/billing/subscribe` returns that URL (`managed_pricing: true`)
- Quota still synced via `APP_SUBSCRIPTIONS_UPDATE` when Shopify sends plan name containing free/starter/growth

## Partner checklist

1. App Pricing plans named so normalize finds `starter` / `growth` / `free` (e.g. “Starter”, “AdFeed Starter”)
2. Production `SHOPIFY_APP_HANDLE` matches Admin URL slug (e.g. `adfeed-ai` or `adfeed-ai-3`)
3. Full deploy: API + `adfeed-web` rebuild (not landing-only)
4. Record: open Plans → Choose on Shopify → approve → return
5. Mark resolved + demo screencast
