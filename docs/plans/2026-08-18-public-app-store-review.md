# Public App Store Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make AdFeed AI pass public Shopify App Store review without changing Feed field owners.

**Architecture:** Production App URL and webhooks on `https://deltfu.com`. FastAPI verifies HMAC, implements GDPR erase, bills via Shopify Billing API, and talks to Admin **GraphQL only**. App Home stays Preact + Polaris. Remove template Sidekick FAQ tools before submit.

**Tech Stack:** FastAPI, `store_db` SQLite, Shopify Admin GraphQL, App Home UI extension, `shopify.app.toml`.

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Design: docs/plans/2026-08-18-public-app-store-review-design.md
```

**Do not:** invent GTIN/brand, add `pin_*` / `_enhance_title` layers, request `write_products` or customer scopes, promise GMC approval in copy.

---

### Task 1: GDPR HMAC + shop purge (tests first)

**Files:**
- Modify: `phase0/adfeed/shopify_webhooks.py`
- Modify: `phase0/adfeed/store_db.py` (add `purge_store_data`)
- Modify: `phase0/adfeed/api.py` (`_webhook_gdpr` / shop_redact)
- Create: `phase0/tests/test_gdpr_webhooks.py`

**Step 1: Failing tests**

```python
def test_invalid_hmac_returns_401(client):
    res = client.post("/api/webhooks/shopify/shop_redact", content=b"{}", headers={
        "X-Shopify-Hmac-Sha256": "nope",
        "X-Shopify-Topic": "shop/redact",
        "X-Shopify-Shop-Domain": "gone.myshopify.com",
    })
    assert res.status_code == 401

def test_shop_redact_deletes_store_and_products(client, store_with_product):
    # valid HMAC for body; after handler, get_store_by_domain is None
    ...
```

Run: `cd phase0 && python -m pytest tests/test_gdpr_webhooks.py -v`  
Expected: FAIL (no purge, HMAC skippable).

**Step 2: Implement**

- `purge_store_data(shop_domain)`: delete variants/products/jobs/feed_configs/feed_files rows for that store; unlink feed XML/CSV under `feeds/{store_id}/`; delete store row (or anonymize if FK forces keep — prefer hard delete).
- `handle_shop_redact(payload)` calls purge.
- `customers/data_request` and `customers/redact`: log shop + customer id, return `{"ok": true, "stored_customer_pii": false}`.
- HMAC: if `SHOPIFY_CLIENT_SECRET` set, invalid/missing HMAC → 401. `ADFEED_WEBHOOK_SKIP_HMAC` only when secret **empty** (unit tests). Never skip when secret is present.

**Step 3: Tests pass. Do not commit unless the user asks.**

---

### Task 2: Subscribe compliance webhooks in toml + production URLs

**Files:**
- Modify: `phase0/add-feed-ai/shopify.app.toml`

Replace tunnel URLs with production:

```toml
application_url = "https://deltfu.com"
embedded = true

[webhooks]
api_version = "2026-10"

  [[webhooks.subscriptions]]
  compliance_topics = [ "customers/data_request", "customers/redact", "shop/redact" ]
  uri = "https://deltfu.com/api/webhooks/shopify/compliance"

  [[webhooks.subscriptions]]
  topics = [ "app/uninstalled" ]
  uri = "https://deltfu.com/api/webhooks/shopify/app_uninstalled"

  [[webhooks.subscriptions]]
  topics = [ "products/update" ]
  uri = "https://deltfu.com/api/webhooks/shopify/products_update"

  [[webhooks.subscriptions]]
  topics = [ "products/delete" ]
  uri = "https://deltfu.com/api/webhooks/shopify/products_delete"

  [[webhooks.subscriptions]]
  topics = [ "app_subscriptions/update" ]
  uri = "https://deltfu.com/api/webhooks/shopify/app_subscriptions_update"

[auth]
redirect_urls = [ "https://deltfu.com/api/shopify/callback" ]
```

**Files:**
- Modify: `phase0/adfeed/api.py` — add `POST /api/webhooks/shopify/compliance` that reads `X-Shopify-Topic` and dispatches (keep old three routes as aliases).

Local tunnel: document in `phase0/add-feed-ai/README.md` that `shopify app dev` may rewrite URLs locally; **released version for review must be deltfu.com**.

Deploy app config: `cd phase0/add-feed-ai && shopify app deploy --allow-updates --version adfeed-ai-N --message "production URLs + GDPR compliance webhooks"` **after** API is live on deltfu.com.

---

### Task 3: Privacy + support pages

**Files:**
- Create: `phase0/adfeed/legal_pages.py` or static HTML served by FastAPI
- Modify: `phase0/adfeed/api.py` — `GET /privacy`, `GET /support`

English pages (listing primary language is English):

- What we collect: shop domain, access token, product catalog snapshots, generated feeds, ad brand the merchant confirms.
- What we do **not** collect: customer PII, order data, payment card data.
- Retention: shop data kept while installed; erased on `shop/redact` (≈48h after uninstall).
- Contact: support email (fill real inbox; placeholder `support@deltfu.com` only if that mailbox exists).
- No GMC approval guarantee.

Partner Dashboard: paste `https://deltfu.com/privacy` into Privacy policy URL; add emergency developer email + phone.

---

### Task 4: In-app billing upgrade/downgrade

**Files:**
- Modify: `phase0/adfeed/api.py` — `BillingSubscribeBody.test` default from env `ADFEED_BILLING_TEST` (`"true"` only in local). Production server env: `ADFEED_BILLING_TEST=false`.
- Modify: `phase0/adfeed/shopify_billing.py` — `create_app_subscription(..., test=None)` reads env.
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx` — when `billing.quota_remaining` too low **or** on free plan, show Starter / Growth buttons that `POST /api/app/billing/subscribe` then open `confirmation_url` (s-link / s-button `href`, not popup).
- Modify: locales `en.default.json`, `zh-CN.json`, `i18n-messages.js` — plan names, prices, “Change plan”. Merchant must switch plans without reinstall.
- Test: `phase0/tests/test_shopify_billing.py` — subscribe growth when already starter still returns confirmation_url; production default test flag false when env unset.

Return URL: `https://deltfu.com/api/app/billing/return` must bounce merchant back into embedded app (or App Home). If return handler missing, add one that redirects to Admin app.

---

### Task 5: Admin REST → GraphQL (production paths)

**Files:**
- Create: `phase0/adfeed/shopify_admin_gql.py` — `graphql(shop, token, query, variables)`, `fetch_shop`, `iter_products`, `fetch_product`, `fetch_policies`.
- Modify: `phase0/adfeed/shopify_client.py`, `store_sync.py`, `store_compliance.py`, `feed_image.py`, `pipeline.py` — delete `.../admin/api/.../products.json` and `shop.json` and `policies.json` HTTP GETs.
- Leave local scripts (`phase0/shopify_feed.py`, `scripts/seed_and_preview_feed.py`) until last; they are not the public app. Prefer migrating them too so a repo grep for `/products.json` is empty.
- Tests: `phase0/tests/test_shopify_admin_gql.py` with httpx/respx or monkeypatched `requests.post` returning GraphQL JSON shaped like current REST parsers expect.

Keep Python return shapes stable so pipeline/sync tests do not churn.

**Do not add scopes** unless a GraphQL field errors in staging. `read_products` must remain the only toml scope unless policies query is denied — then add `read_legal_policies` and document why in listing.

---

### Task 6: Remove Sidekick FAQ template

**Files:**
- Remove or stop shipping: `phase0/add-feed-ai/extensions/app-tools/` (FAQ `list_faqs` / `get_faq` is not AdFeed).
- If CLI requires the folder, replace `tools.json` + `instructions.md` with **no tools** only if empty extensions are allowed; otherwise delete the extension from the app and deploy so review app has no Sidekick mismatch.

Verify `shopify.app.toml` / app version no longer includes FAQ tools.

---

### Task 7: Listing copy + assets (Partner Dashboard, not Feed code)

English listing (no stats, no “best/only/guarantee”):

- **Subtitle:** Generate Google Shopping feeds from your Shopify catalog  
- **Details:** Cleans titles, flags missing color/size, lets you pick an ad image, gives a persistent feed URL. Does not guarantee Google Merchant Center approval.  
- **Pricing:** Free quota (20 generate units) / Starter $14.99/mo (150) / Growth $39/mo (400). Match `shopify_billing.py`.  
- **Icon:** 1200×1200 PNG, no Shopify logo, no prices on the icon.  
- **Screenshots:** real App Home — generate, product list, fix color/size, copy feed URL. No desktop wallpaper, no duplicate shots.  
- **Screencast:** English (or English subtitles), install → generate → copy URL.  
- **Test instructions:** “Install on the review store. Confirm ad brand. Select products. Click generate. Copy the Google US feed URL. To test billing, choose Starter and approve the charge. To test size fix, open a product flagged missing size.”  
- **Languages:** English + Chinese only if UI is complete (it is).  
- **Tags:** marketing / product feeds — not sales channel.  
- **Opt out** Protected customer data.

Replace repo `phase0/add-feed-ai/SECURITY.md` Shopify HackerOne boilerplate with a pointer to `/privacy` (optional; listing URL is what review checks).

---

### Task 8: Production deploy + review dry-run

1. Deploy FastAPI to `deltfu.com` (`deploy-from-local.sh --backend-only` or equivalent). Confirm `https://deltfu.com/privacy` and HMAC 401 on bad webhook.  
2. `shopify app deploy` with production toml.  
3. On a **development store in the same Partner org**: uninstall if installed → install from App Store listing preview → OAuth → App Home loads → billing plan click → generate feed → uninstall → wait/trigger `shop/redact` via `shopify app webhook trigger` if available.  
4. Confirm no 404/500, no tunnel host in Network tab.  
5. Partner Dashboard → App Store review → run automated checks → submit.

**Stop and report** if SSH to deltfu.com still fails (previous publickey error): production URL cannot go live until that is fixed; do not submit with trycloudflare URLs.

---

## Out of scope (reject if a later session tries to sneak them in)

- Title/color/size generator changes, Magic Bar, watermark removal  
- `write_products`, fake GTIN, silent `eprolo` brand  
- Built for Shopify extra checklist  
