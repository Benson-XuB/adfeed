# Shopify App Multi-Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ship an App-only AdFeed product: select Shopify products, multi-select Google/Meta/TikTok × markets, generate durable feeds with layered AI, billed via Shopify Billing as SKU×platform×language.

**Architecture:** Embedded Shopify App is the only UI. Backend verifies session tokens, persists everything in `store_db`, runs Approach-3 AI (shared attrs → per-language skeleton → per-platform rewrite), writes public feed URLs, syncs plan/quota from Shopify Billing webhooks. Legacy Web SaaS/CSV entry points are removed or disabled.

**Tech Stack:** Shopify App (Preact/React extension or app-home), FastAPI, SQLite `store_db`, existing AI pipeline modules, Shopify Billing + webhooks, Nginx for `/feeds/`.

**Design doc:** `docs/plans/2026-08-06-shopify-app-multi-platform-design.md`

---

### Task 1: Freeze design decisions in store schema

**Files:**
- Modify: `phase0/adfeed/store_db.py`
- Create: `phase0/tests/test_store_schema.py`

**Step 1: Write failing tests for new tables/columns**

```python
def test_store_has_billing_and_quota_fields():
    store = create_store(shop_domain="x.myshopify.com", ...)
    assert hasattr(store, "quota_total")
    assert hasattr(store, "quota_used")

def test_product_assets_unique_key():
    # product_id + platform + language unique
    ...
```

**Step 2: Run test — expect fail**

**Step 3: Extend schema**

Add/ensure:
- `stores`: `plan`, `quota_total`, `quota_used`, `subscription_id`, `billing_status`
- `product_assets`: `product_id`, `platform`, `language`, `title`, `description`, `tags_json`, `updated_at`
- `usage_ledger`: `store_id`, `job_id`, `sku`, `platform`, `language`, `created_at`
- store-scoped `jobs`: status, totals, error

**Step 4: Tests pass → commit**

```bash
git add phase0/adfeed/store_db.py phase0/tests/test_store_schema.py
git commit -m "feat(store_db): billing quota and product_assets schema"
```

---

### Task 2: Session auth middleware for App APIs

**Files:**
- Create: `phase0/adfeed/shopify_auth.py`
- Modify: `phase0/adfeed/api.py`
- Create: `phase0/tests/test_shopify_session.py`

**Step 1: Failing test — request without session → 401**

**Step 2: Implement Shopify session token verification** (JWT from App Bridge / Authorization header), resolve `shop` → `stores` row

**Step 3: Protect all `/api/app/*` routes; reject legacy open generate endpoints

**Step 4: Commit**

```bash
git commit -m "feat(auth): require Shopify session for app APIs"
```

---

### Task 3: App API — products + billing status

**Files:**
- Modify: `phase0/adfeed/api.py`
- Modify: `phase0/adfeed/shopify_client.py`
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx`
- Modify: `phase0/add-feed-ai/shared/models/products.ts` (replace localhost)

**Step 1: `GET /api/app/products`** — fetch via store token, map to list DTO, optional cache in `products`

**Step 2: `GET /api/app/billing/status`** — return plan, quota_total, quota_used, remaining

**Step 3: App Home reads both; show quota bar; remove hard-coded `http://localhost:8000` → `BACKEND_URL` env

**Step 4: Commit**

```bash
git commit -m "feat(app): products list and billing status endpoints"
```

---

### Task 4: Shopify Billing subscribe + webhook

**Files:**
- Create: `phase0/adfeed/shopify_billing.py`
- Modify: `phase0/adfeed/api.py`
- Create: `phase0/tests/test_shopify_billing.py`

**Step 1: `POST /api/app/billing/subscribe`** creates recurring charge / subscription confirmation URL

**Step 2: Webhook `APP_SUBSCRIPTIONS_UPDATE`** updates `stores.plan`, `quota_total`, `billing_status`

**Step 3: Map Starter/Growth plan IDs → quota numbers (env-configurable)

**Step 4: Commit**

```bash
git commit -m "feat(billing): Shopify subscriptions and quota sync"
```

---

### Task 5: Quota estimate + enforce (SKU × platform × language)

**Files:**
- Create: `phase0/adfeed/quota.py`
- Modify: `phase0/adfeed/api.py`
- Create: `phase0/tests/test_quota.py`

**Step 1: `estimate_cost(sku_count, platforms, languages) -> int`**

**Step 2: Generate endpoint rejects when `estimate > remaining` with clear error**

**Step 3: After successful asset writes, `debit_quota` + `usage_ledger` rows

**Step 4: Commit**

```bash
git commit -m "feat(quota): estimate and debit SKU x platform x language"
```

---

### Task 6: Approach-3 AI pipeline

**Files:**
- Modify: `phase0/adfeed/pipeline.py` (`optimize_for_store` or new `optimize_layered`)
- Modify: `phase0/adfeed/title_optimizer.py` (platform-specific rewrite helpers)
- Create: `phase0/tests/test_layered_optimize.py`

**Step 1: Shared pass** — GPC + attributes once per product

**Step 2: Language pass** — skeleton title/description/tags per language

**Step 3: Platform pass** — rewrite into Google / Meta / TikTok asset rows in `product_assets`

**Step 4: Watermark** — only if flag true; call existing `image_processor`

**Step 5: Commit**

```bash
git commit -m "feat(ai): layered optimize shared+language+platform"
```

---

### Task 7: Multi-platform feed writers + durable URLs

**Files:**
- Modify: `phase0/adfeed/multi_platform_feeds.py`
- Modify: `phase0/adfeed/pipeline.py` (`generate_feed_for_store`)
- Modify: `phase0/adfeed/api.py` (public feed routes)
- Modify: `nginx/deltfu-feeds.conf` if needed

**Step 1: For each platform × language selected, write feed file under `FEEDS_DIR/{store_id}/{platform}/{lang}.{xml|csv}`**

**Step 2: Register in `feed_files`; return absolute HTTPS URLs**

**Step 3: Public GET serves latest file (GMC/Meta/TikTok polling)

**Step 4: Commit**

```bash
git commit -m "feat(feeds): durable Google/Meta/TikTok URLs per language"
```

---

### Task 8: `POST /api/app/generate` job + App Home UI

**Files:**
- Modify: `phase0/adfeed/api.py`
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx`
- Modify: `phase0/add-feed-ai/extensions/app-home/src/AppHome.jsx` if needed

**Step 1: Request body** `{ product_ids, platforms, languages, remove_watermarks }`

**Step 2: Defaults server-side too: platforms=`["google"]`, languages=`["US"]`**

**Step 3: Background job updates progress; UI polls `GET /api/app/jobs/{id}`**

**Step 4: UI: checkboxes, live estimate, quota bar, result URL list**

**Step 5: Commit**

```bash
git commit -m "feat(app): generate job UI with defaults Google+US"
```

---

### Task 9: Webhooks — catalog + uninstall + GDPR stubs

**Files:**
- Modify: `phase0/adfeed/api.py`
- Create: `phase0/adfeed/shopify_webhooks.py`

**Step 1: Verify HMAC on all webhooks**

**Step 2: `products/update|delete` refresh or soft-disable products**

**Step 3: `app/uninstalled` revoke token, mark store inactive**

**Step 4: GDPR endpoints return 200 with TODO persistence if needed for review**

**Step 5: Commit**

```bash
git commit -m "feat(webhooks): product sync, uninstall, GDPR stubs"
```

---

### Task 10: Delete / disable redundant Web SaaS paths

**Files:**
- Modify or remove: `phase0/web/` product routes (or replace with static landing “Install Shopify App”)
- Modify: `phase0/adfeed/api.py` — disable `/api/upload`, magic-link, PayPal activate, open `/api/shopify/feed`
- Update README / landing copy

**Step 1: Feature-flag or remove upload + Google-user auth from serving path**

**Step 2: Ensure App path does not import dead code**

**Step 3: Smoke: health + app session + generate dry-run**

**Step 4: Commit**

```bash
git commit -m "chore: retire web SaaS upload/auth as primary product"
```

---

### Task 11: End-to-end verification

**Steps:**
1. Install app on dev store
2. Subscribe test plan
3. Select 3 products, Google+Meta, US+DE → estimate 12
4. Generate → 4 feed URLs
5. Confirm quota used += 12
6. Confirm unauthenticated generate returns 401
7. Confirm watermark off skips image pipeline

**Commit:** only if verification scripts/docs added

```bash
git commit -m "docs: e2e checklist for app multi-platform generate"
```

---

## Out of scope (YAGNI for this plan)

- Rebuilding full Web dashboard parity
- Platform-specific image creative generation
- Auto-push into GMC/Meta/TikTok APIs (feeds only)
- Changing AI long-tail quality rules beyond platform rewrite prompts
