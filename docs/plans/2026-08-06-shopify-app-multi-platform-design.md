# AdFeed AI — Shopify App Multi-Platform Design

**Date:** 2026-08-06  
**Status:** Approved  
**Product form:** Shopify App only (no Web SaaS)

---

## 1. Product shape

Primary surface is the **Shopify embedded App**. Merchants install the app, select products, choose ad platforms and markets/languages, then generate durable feed URLs.

Web SaaS (Google login, Magic Link, CSV upload, PayPal web billing) is **removed or demoted**. Optional watermark removal stays behind a default-off switch using existing `image_processor` logic.

### Default UX

- Platform: **Google** checked by default; Meta and TikTok multi-select
- Market/language: **US** checked by default; DE / FR / ES / IT multi-select
- Quota bar always visible: plan, used, remaining
- Before Generate: show estimated cost `SKU × platforms × languages`
- Insufficient quota: **block** and prompt upgrade (do not silently partial-generate)

### Main flow

```
Install App
  → Shopify Billing subscribe
  → Load product list
  → Select products
  → Select platforms (default Google)
  → Select markets (default US)
  → Optional: remove watermarks (off)
  → Show estimated quota burn
  → Generate
  → Durable feed URLs per platform × language
```

---

## 2. AI strategy (Approach 3)

Billing is **SKU × platform × language**, but compute is layered to avoid waste:

1. **Shared once per SKU:** GPC match, gender/size/attributes, base compliance
2. **Once per SKU × language:** cultural long-tail skeleton, scene words, base description
3. **Once per SKU × platform × language:** platform-specific title/description rewrite  
   - Google: front_70 + rest Shopping rules  
   - Meta: commerce catalog title/hooks  
   - TikTok: short, shoppable ecommerce phrasing

Quota is charged for each successfully written `product_assets` row (platform × language). Failed SKUs do not consume quota for that combination.

---

## 3. Data model (single source of truth)

Only `store_db` (evolve schema as needed):

| Table | Role |
|-------|------|
| `stores` | Shop domain, access token, billing plan, quota_total, quota_used, subscription id |
| `products` / `variants` | Raw Shopify catalog snapshot |
| `product_assets` | Optimized copy keyed by `product_id + platform + language` |
| `feed_files` | Durable path + updated_at per store/platform/language |
| `usage_ledger` | Per-generate debit lines for audit |
| `jobs` (store-scoped) | Async generate progress |

Identity = Shopify shop / session. No separate Google-user user table for the product path.

---

## 4. App UI

App Home is the only workbench:

1. Header: shop name + `Used / Total / Remaining` + Upgrade
2. Product multi-select with search/pagination
3. Platform checkboxes: Google (default), Meta, TikTok
4. Market checkboxes: US (default), DE, FR, ES, IT
5. Optional watermark toggle (default off)
6. Live estimate: `N SKU × P platforms × L langs = cost`
7. Generate → progress → result URLs to copy into GMC / Meta Commerce / TikTok catalog

---

## 5. Billing

- Use **Shopify Billing API** (recurring subscriptions)
- Plans map to monthly quota (reuse Starter/Growth style numbers)
- Webhooks: `APP_SUBSCRIPTIONS_UPDATE` sync plan + quota
- Unsubscribed / expired: keep existing feeds readable; block new Generate
- Free tier: tiny allowance (e.g. 10) then upgrade CTA

---

## 6. API boundary (App-only backend)

All routes require verified Shopify session (or webhook HMAC).

| Endpoint | Purpose |
|----------|---------|
| Session auth middleware | Reject unauthenticated calls |
| `GET /api/app/products` | List/cache products |
| `GET /api/app/billing/status` | Plan + quota |
| `POST /api/app/billing/subscribe` | Create confirmation URL |
| `POST /api/app/generate` | Start generate job |
| `GET /api/app/jobs/{id}` | Progress + feed URLs |
| `GET /feeds/{store_id}/{platform}/{lang}.*` | Public durable feeds |
| Webhooks | products update, app/uninstalled, billing, GDPR |

Remove or lock down legacy open endpoints such as unauthenticated `/api/shopify/feed`. Replace hard-coded `localhost:8000` with env-based API URL.

---

## 7. Cleanup / delete list

| Remove or hide | Why |
|----------------|-----|
| `phase0/web` auth/upload/PayPal dashboard as product | App-only |
| Web `users` / magic_links / upload jobs as primary auth | Replaced by `stores` + Shopify session |
| Dual Web Shopify OAuth connect UI | Managed install + session |
| CSV upload as primary nav | Optional internal tooling only |

| Keep | Why |
|------|-----|
| `pipeline` AI core, `cultural_context`, title optimizer | Quality engine |
| `multi_platform_feeds` | Meta/TikTok emitters |
| `image_processor` | Optional watermark path |
| `store_db` + App Home | Product spine |

---

## 8. Error handling

- Per-SKU failures isolated; batch continues
- Job status shows ok/fail counts
- Quota debit only after successful asset write
- Network/LLM retries with bounded backoff; then mark SKU failed

---

## 9. Success criteria

1. Merchant installs app, subscribes, generates Google-US feed without leaving Admin
2. Multi-select Meta/TikTok + extra languages produces distinct durable URLs
3. Quota UI accurate before/after generate
4. No unauthenticated generate path
5. Web CSV/login path no longer required for the happy path

---

## Decisions log

- Product surface: **A — Shopify App only**
- Billing: **A — Shopify Billing API**
- Selection order: platforms + markets multi-select; defaults Google + US
- Quota unit: **C — SKU × platform × language**
- AI approach: **3 — shared GPC/attrs + per-language skeleton + per-platform rewrite**
- Watermark: optional, default off
- Insufficient quota: block (not silent truncate)
