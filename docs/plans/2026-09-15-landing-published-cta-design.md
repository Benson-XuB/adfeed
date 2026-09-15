# Landing published CTA — design

**Date:** 2026-09-15  
**Status:** Approved (option B)

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## Goal

App Store listing is **published / fully visible**. Marketing site CTAs must stop saying waitlist / early access and point to install.

**Canonical install URL:** `https://apps.shopify.com/adfeed-ai-1`  
**Primary label:** Install on Shopify

## Scope (B)

- Homepage + all tools / guides / setup CTAs
- Remove waitlist email forms from visible pages
- Keep `/api/waitlist` + `waitlist.js` on disk (unused) to avoid backend churn

## Out of scope

- Embedded Shopify App UI
- Pricing / product narrative changes
- Push-to-Google re-enable

## Deploy

`deploy-landing-only.sh` only.
