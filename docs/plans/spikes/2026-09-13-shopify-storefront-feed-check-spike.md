# Spike: Shopify storefront → Google Shopping risk check

**Date:** 2026-09-13  
**Status:** ACCEPTED for thin MVP (public `products.json` only)

## Questions

| # | Answer |
|---|--------|
| 1. Can we use `https://{shop}.myshopify.com/products.json`? | **Yes** for many stores. Paginate `limit=50&page=N`. Some stores disable password / lock catalog → 404/401. |
| 2. What can we infer without Admin API? | Title quality, vendor dirty-brand heuristics, images present, color/size **option names**, variant count, price strings on variants. |
| 3. What we cannot? | Real GTIN/MPN, GMC disapproval, inventory truth, draft products, Markets pricing, metafields. |
| 4. Abuse limits | Cap 5 pages × 50 = 250 products; User-Agent identify; timeout 25s; no store of catalog. |

## Thin MVP shipped

- API: `POST /api/public/shopify-check` `{ "shop": "foo.myshopify.com" }`
- Page: `/tools/shopify-checker`
- CTA waitlist `utm_medium=shopify-checker`

## Non-goals

- Admin OAuth this week
- Writing products or inventing GTIN/brand
