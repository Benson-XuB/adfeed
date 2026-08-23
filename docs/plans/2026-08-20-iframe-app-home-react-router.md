# iframe App Home (React Router) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace Custom-only App Home UI extension as the merchant entry with an official Shopify React Router embedded iframe app that calls existing FastAPI, without changing Feed field owners.

**Architecture:** Scaffold `phase0/add-feed-ai/web` from Shopify’s React Router template; App Bridge session JWT → FastAPI `/api/app/*`; migrate Home + Plans UX from Preact App Home into Polaris React routes; keep `phase0/adfeed` as source of truth for feeds/billing/GDPR.

**Tech Stack:** Shopify React Router template (`@shopify/shopify-app-react-router`), Polaris React, existing FastAPI + `store_db`, Cloudflare tunnel / `shopify app dev` for local HTTPS.

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Design: docs/plans/2026-08-20-iframe-app-home-react-router-design.md
```

**Do not:** invent GTIN/brand; add title/color pin layers; deploy deltfu in this plan; delete FastAPI.

---

### Task 1: Scaffold React Router web app into the existing app

**Files:**
- Create: `phase0/add-feed-ai/web/` (from official template)
- Modify: `phase0/add-feed-ai/package.json` (workspace / scripts if needed)
- Modify: `phase0/add-feed-ai/shopify.app.toml` (ensure `[webhooks]` / scopes unchanged; note `application_url` will point at web later)

**Step 1: Scaffold beside extensions (do not wipe extensions yet)**

From `phase0/add-feed-ai`:

```bash
# Prefer linking into existing Partner app client_id ac2bf432…
shopify app init --template=https://github.com/Shopify/shopify-app-template-react-router
```

If CLI forces a new folder, generate into a temp dir then move the `web`/`app` tree into `phase0/add-feed-ai/web` so **one** `shopify.app.toml` and **one** client_id remain.

**Step 2: Verify template boots**

```bash
cd phase0/add-feed-ai && shopify app info
```

Expected: web package listed; client_id still `ac2bf432a87c7e12cb7c439556fe762b`.

**Step 3: Commit scaffold only when user asks** (do not commit secrets `.env`).

---

### Task 2: Wire Backend URL + session token client

**Files:**
- Create: `phase0/add-feed-ai/web/app/lib/backend.server.ts` (optional server proxy) **or**
- Create: `phase0/add-feed-ai/web/app/lib/adfeed-api.ts` (browser fetch with Bearer)
- Modify: FastAPI CORS in `phase0/adfeed/api.py` only if web origin missing

**Step 1: Client helper**

```ts
// adfeed-api.ts — mirror shared/models/products.ts endpoints
export async function backendFetch(path: string, token: string, init: RequestInit = {}) {
  const base = (import.meta.env.VITE_BACKEND_URL || process.env.BACKEND_URL || "").replace(/\/$/, "");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  return fetch(`${base}${path}`, { ...init, headers });
}
```

**Step 2: Smoke from a loader/action**

In a throwaway route or `app._index` loader: call `GET /api/health` (no auth) and `GET /api/app/billing/status` with session token from `authenticate.admin` → exchange or pass idToken.

Preferred: use App Bridge `idToken` on client (same as App Home) so FastAPI `require_store` unchanged.

**Step 3: Manual check**

With API + tunnel up, open embedded app; Network shows Bearer to tunnel `/api/app/bootstrap` → 200.

---

### Task 3: Nav shell — Home + Plans routes

**Files:**
- Modify: `phase0/add-feed-ai/web/app/routes/app.tsx` (NavMenu)
- Create: `phase0/add-feed-ai/web/app/routes/app._index.tsx` (placeholder Home)
- Create: `phase0/add-feed-ai/web/app/routes/app.plans.tsx` (placeholder Plans)

**Step 1: NavMenu**

```tsx
<NavMenu>
  <Link to="/app" rel="home">Home</Link>
  <Link to="/app/plans">Plans</Link>
</NavMenu>
```

**Step 2: Placeholders**

Each page shows heading + “AdFeed iframe shell OK”.

**Step 3: Manual** — both routes load inside Admin iframe without losing session.

---

### Task 4: Port bootstrap + brand + product select + generate (MVP path)

**Files:**
- Modify: `web/app/routes/app._index.tsx` (grow into real Home)
- Create: `web/app/lib/adfeed-api.ts` endpoints: bootstrap, connection, brand, products, estimate, generate, job poll, feeds
- Reference: `extensions/app-home/src/pages/HomePage.jsx` for UX order only

**Step 1: Bootstrap on mount**

Call `POST /api/app/bootstrap` then `GET /api/app/billing/status` + product list (Admin GraphQL or `/api/app/products`).

**Step 2: Brand gate**

Confirm ad brand via `PATCH /api/app/store/brand` before generate enabled.

**Step 3: Generate**

`POST /api/app/generate` → poll job → show feed URL list + copy button.

**Step 4: Manual acceptance**

Google + US, ≥1 product → generate → copy XML URL opens feed (tunnel or local public URL).

**Do not** port every quality/image panel in this task — only happy path.

---

### Task 5: Port Plans page + subscribe

**Files:**
- Modify: `web/app/routes/app.plans.tsx`
- Use: `POST /api/app/billing/subscribe`

**Step 1: Three plan cards** (Free / Starter / Growth) matching `shopify_billing.py` prices/quotas.

**Step 2: Subscribe** opens `confirmation_url` via App Bridge / top-level navigation (not popup blockers).

**Step 3: Manual** with `ADFEED_BILLING_TEST=true` — either Shopify test charge or documented Partner Distribution error surfaced cleanly.

---

### Task 6: Port remaining Home panels (quality / size-color / market lock)

**Files:**
- Modify: `web/app/routes/app._index.tsx`
- Port i18n strings from `extensions/app-home/src/i18n-messages.js`

**Order:**

1. Feed cards at top  
2. Market select + lock banner (`/api/app/market-ready`)  
3. Inline size/color patch + bulk patch  
4. Store compliance todos  

Stop if a panel blocks MVP; ship behind “phase 2” comment only if user agrees — default is port all merchant-visible panels before calling iframe done.

---

### Task 7: Point application_url at web; retire extension as primary home

**Files:**
- Modify: `shopify.app.toml` — `application_url` / `auth.redirect_urls` to web HTTPS  
- Modify: `extensions/app-home/shopify.extension.toml` — remove or comment `admin.app.home.render` **before** public submit  
- Update: `docs/app-store-listing/TESTING.md` — “embedded React Router App Home”

**Step 1: Local** — after deploy/dev, opening Apps → AdFeed shows iframe web, not extension-only and not FastAPI `/` HTML stub.

**Step 2: Keep FastAPI `GET /` stub** for health confusion avoidance, but it must not be the App URL.

**Step 3: Manual** hard refresh Admin; confirm no `visibleFeeds` / Preact extension as sole UI.

---

### Task 8: Local stack docs + CORS smoke

**Files:**
- Modify: `phase0/scripts/local_shopify_stack.sh` — print web + API steps  
- Modify: `phase0/add-feed-ai/README.md` — iframe local runbook  
- Test: `phase0/tests/test_gdpr_webhooks.py` still passes (no regression)

**Step 1:** Document: API → tunnel → `shopify app dev` / deploy web.

**Step 2:**

```bash
cd phase0 && .venv/bin/python -m pytest tests/test_gdpr_webhooks.py tests/test_shopify_billing.py -q
```

Expected: pass.

---

## Out of scope (later)

- Production deltfu cutover  
- Pixel-perfect clone of every Polaris `s-*` quirk  
- Rewriting pipeline in Node  

## Milestone definition of done

Merchant on local embedded iframe can: install/open app → confirm brand → generate US Google feed → copy link → open Plans. Extension is no longer required for that path.
