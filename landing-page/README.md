# AdFeed AI landing (static)

English marketing site for App Store V1.0 capabilities.

## Preview locally

Waitlist signup needs the API. Use the dev server (proxies `/api/*` like production nginx):

```bash
# Terminal 1 — API
cd phase0
.venv/bin/uvicorn adfeed.api:app --reload --port 8000

# Terminal 2 — landing + /api proxy
cd landing-page
python3 dev_server.py
# open http://127.0.0.1:8765/
```

Static-only preview (no waitlist POST):

```bash
cd landing-page
python3 -m http.server 8765
```

## Production

Served on **https://deltfu.com/** (nginx). Static files under `/lp-assets/` and `/styles.css` so they do not clash with the Shopify app’s `/assets/`. App routes (`/app`, `/auth`, …) and `/api/*` are unchanged. Listing privacy/support stay at `/privacy` and `/support` (FastAPI); marketing copies are `/privacy.html` and `/support.html`.

## Pages

| File | Purpose |
|------|---------|
| `index.html` | Marketing home: hero, trust, demo, 3-step how, pricing, waitlist |
| `setup.html` | Full Merchant Center setup guide (6 steps) |
| `privacy.html` | Privacy Policy |
| `terms.html` | Terms of Use |
| `support.html` | Support + FAQ · support@deltfu.com |
| `waitlist.js` | Shared early-access form handler |

## Do not

- Do not `shopify app deploy` from this folder.
- Do not claim Google API push / Ads metrics as the primary product until those ship in production listing.

## Design

`docs/plans/2026-09-01-adfeed-landing-page-design.md`
