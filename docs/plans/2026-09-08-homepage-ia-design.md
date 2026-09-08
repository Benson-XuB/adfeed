# Homepage IA 收口 Design（Option A）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**Status:** ACCEPTED 2026-09-08  
**Scope:** Marketing homepage only (`landing-page/`). No App, no new guides/tools.

## Problem

Pages look good in isolation but lack one user path. Nav competes (Demo / Setup / Tools / Guides). Hero stacks four messages. Billing says “generate units” before “products.”

## Product spine

```
Diagnose → Fix → Generate → Publish
```

- Free tools = Diagnose  
- AdFeed = Fix + Generate  
- Merchant Center paste URL = Publish  

## Decisions

1. **Keep H1 locked:** `From 1688 → Shopify → Google Shopping`
2. **Nav:** Free tools · How it works · Pricing · Guides · [Get early access]  
   Drop primary: Demo, Setup guide
3. **Hero:** one benefit line + trust row + waitlist + secondary “Check my feed”; Before/After **below** first-screen CTA block
4. **Diagnose band:** two cards → Disapproval Checker + Feed Checker
5. **Trust / Decide:** keep “what we never do”; clarify fix vs never
6. **How it works:** Confirm **product** brand → Generate clean feed → Paste one URL; demo video lives here; remove standalone Demo section
7. **Pricing:** “Up to N products × markets / month”; generate-unit math → FAQ/footnote
8. **Out of scope:** Guides SEO cluster, new articles, App UI

## Success

New visitor can answer in order: who it’s for → what to do first (diagnose or waitlist) → how AdFeed works → what it costs—without hunting Demo/Setup in the nav.
