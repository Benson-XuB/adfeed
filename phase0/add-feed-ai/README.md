# AdFeed AI — Shopify embedded app (iframe App Home)

Field contract: `docs/plans/2026-08-14-feed-field-contract.md`  
North Star: `docs/plans/2026-08-12-mvp-north-star.md`

Public App Store entry is the **React Router** app in `web/`. FastAPI in `../adfeed` remains the feed/billing/GDPR API. The old Preact App Home UI extension lives in `_retired/app-home` (not deployed).

## Layout

| Path | Role |
|------|------|
| `web/` | Embedded iframe App Home (Shopify React Router + Polaris) |
| `extensions/app-tools` | Admin tools extension (Sidekick) |
| `_retired/app-home` | Former `admin.app.home.render` UI (reference only) |
| `shared/` | Shared helpers still used by retired extension |
| `../adfeed` | FastAPI backend |

## Local runbook

### 1. Start API + tunnel

```bash
cd phase0 && ./scripts/local_shopify_stack.sh
```

This starts FastAPI on `:8000`, a Cloudflare quick tunnel, and writes:

- `add-feed-ai/.env` → `VITE_BACKEND_URL`
- `add-feed-ai/web/.env` → `VITE_BACKEND_URL` / `BACKEND_URL`
- `shared/local-backend.js` (retired extension)

Keep that terminal alive.

### 2. Run embedded web (preferred)

Needs a Partner **development** store (`shopify app dev` does not work on many Basic plan stores):

```bash
cd phase0/add-feed-ai
shopify app dev -s <your-dev-store>.myshopify.com
```

CLI tunnels the `web/` process, updates `application_url` / auth redirects, and opens the Admin iframe.

Happy path in Admin: confirm ad brand → Google + US → select product → Generate → copy Feed URL → Plans.

### 3. Backend-only smoke

```bash
curl -s "$VITE_BACKEND_URL/api/health"
```

Bearer calls use App Bridge `idToken()` from the iframe (`web/app/lib/adfeed-api.ts`).

## Deploy notes

- `shopify app deploy` ships extensions + app config. You still must **host** the React Router Node server for production `application_url`.
- GDPR / product / billing **webhooks stay on FastAPI**.
- Do not invent GTIN/COGS; do not silent-default brand to eprolo; do not stack title/color in feed_generator.

## Scripts

```bash
npm run typecheck   # web TypeScript
npm run deploy      # shopify app deploy
```
