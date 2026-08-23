# Production cutover checklist (iframe App Home)

Field contract: docs/plans/2026-08-14-feed-field-contract.md  
North Star: docs/plans/2026-08-12-mvp-north-star.md

Blocked until SSH to `deltfu.com` works (2026-08-20: connect timed out).

## When SSH is back

1. Deploy FastAPI: `phase0/deploy-from-local.sh --backend-only`
2. Confirm `ADFEED_BILLING_TEST=false` on server
3. Host React Router (`add-feed-ai/web`): build + `npm run start` behind nginx on `deltfu.com` (or subdomain). Prisma sqlite or migrate session DB as needed.
4. Copy `shopify.app.toml.prod-backup` → `shopify.app.toml` (or `shopify app deploy` with those URLs)
5. `cd phase0/add-feed-ai && shopify app deploy --allow-updates`
6. Dev store: uninstall → install → brand → generate US Google → Plans charge → privacy URL live

## Do not submit review with

- trycloudflare application_url
- ADFEED_BILLING_TEST=true
- App Home still only the retired Preact extension
