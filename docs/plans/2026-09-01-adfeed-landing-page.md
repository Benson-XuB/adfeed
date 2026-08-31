# AdFeed Landing Page Implementation Plan

> **For Claude:** Implement static marketing site; do **not** shopify app deploy.

**Goal:** English marketing site with full how-to for V1.0 feed → Merchant Center, plus Privacy / Terms / Support.

**Architecture:** Static HTML/CSS in `landing-page/`; replace existing dark template; link screenshots from `docs/app-store-listing/screenshots/` or copy into `landing-page/assets/`.

**Tech Stack:** HTML5, CSS (variables, no framework), optional tiny JS for nav/scroll; Google Fonts Fraunces + Source Sans 3.

---

### Task 1: Shared styles + shell
Rewrite `landing-page/styles.css` (light catalog-workshop theme). Shared nav/footer partials inlined per page.

### Task 2: index.html
Hero → audience → features → how-to 6 steps → never-do → pricing → footer. CTAs, real screenshots, motion.

### Task 3: privacy / terms / support
English legal + support@deltfu.com; align with listing honesty (no fake GTIN, no approval guarantee).

### Task 4: Smoke check
Open locally; mobile width; no deploy.

---
