# Google Ads Monitor (marketing tool) — Design

Date: 2026-09-12  
Status: Approved — build now; Developer Token applied by owner later

## Goal

New **marketing-only** tool at `/tools/google-ads-monitor`:
read-only Google Ads shopping performance dashboard (KPI / trends / pre-post / signals / daily table).

## Hard boundaries

- **Do not** change Shopify App (`adfeed-web`), billing, or App OAuth.
- Separate from Merchant Center tool (`/api/public/google/*`).
- New API prefix: `/api/public/google-ads/*`
- Separate session cookie: `adfeed_public_google_ads`

## Config (owner fills later)

```
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_ADS_OAUTH_REDIRECT_URI=https://deltfu.com/api/public/google-ads/oauth/callback
GOOGLE_ADS_DEVELOPER_TOKEN=          # required for live Ads API
GOOGLE_ADS_LOGIN_CUSTOMER_ID=        # optional MCC
```

Without `GOOGLE_ADS_DEVELOPER_TOKEN`: OAuth UI works if client configured; report endpoints return **demo sample** with clear badge. Never pretend live data.

## P0 ship

1. Landing page + report UI (adapted from Doubao demo; AdFeed visual tokens)
2. OAuth start/callback + logout + session cookie
3. `GET /customers` (live or empty + hint)
4. `GET /report?customer_id=&from=&to=&cut=` (GAQL when token present; else sample)
5. nginx pretty URL, sitemap, tools index link
6. landing-only deploy

## Out of scope P0

Write access, bid changes, product-level join to feed SKUs, App Home.
