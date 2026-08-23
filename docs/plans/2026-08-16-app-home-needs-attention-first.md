# App Home Needs-Attention-First Implementation Plan

Field contract: docs/plans/2026-08-14-feed-field-contract.md  
North Star: docs/plans/2026-08-12-mvp-north-star.md  
Design: docs/plans/2026-08-16-app-home-needs-attention-first-design.md

> **For Claude:** Implement task-by-task. UX/IA only — do not change feed field owners.

**Goal:** Reorder App Home so merchants land on「要处理 N」with a small「已可投 M」, Feed links secondary, pipeline collapsed when done.

**Architecture:** Single-file UI reorder in `HomePage.jsx` + i18n catalogs. Reuse existing Multicolor / One Size / I03 / bulk patch / Shopify edit links. No backend API changes.

**Tech Stack:** Preact App Home extension, Polaris web components (`s-*`), `i18n-messages.js` + locale JSON.

---

### Task 1: i18n strings

**Files:**
- Modify: `phase0/add-feed-ai/extensions/app-home/src/i18n-messages.js`
- Modify: `phase0/add-feed-ai/extensions/app-home/locales/en.default.json`
- Modify: `phase0/add-feed-ai/extensions/app-home/locales/zh-CN.json`

Add keys under `overview.*` and CTA variants:
- `overview.heading`, `overview.needsAttention`, `overview.ready`, `overview.noneYet`, `overview.emptyNeeds`, `overview.showFeeds`
- `cta.update`, `cta.selectVisibleGenerate`
- Soften `quality.heading` if needed to「要处理的商品」

### Task 2: Overview counts + primary CTA copy

**Files:**
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx`

- `needsAttentionCount` = unique SKUs in multicolor ∪ oneSize ∪ imageWarn (+1 banner weight for brand unconfirmed / blocked countries as store gates, not SKU-count inflate — show store gate rows separately; N = SKU unique count + storeGates)
- `readyCount` = max(0, (qualityReport.total_rows || sum feed item_count) - unique attention SKUs) — approximate OK
- Page primary button: `cta.update` when `feeds.length > 0`, else `cta.generate`
- After generate completes: `setPipelineOpen(false)`

### Task 3: Reorder sections

**Files:**
- Modify: `HomePage.jsx` render order:

1. Overview bar (when `hasPostGenerate` OR store gates)
2. While `generating`: pipeline expanded
3. Needs-attention block (extract from current quality section — buckets first)
4. Feed links (secondary heading)
5. Quality summary + fatals + tech tables collapsed
6. Setup / products / store warnings
7. Intro only when `!hasPostGenerate`

Add near product toolbar: button「全选当前列表」that selects all `filtered` ids (existing toggleAll may already do this — label as selectVisibleGenerate flow: select filtered then user hits primary).

### Task 4: Deploy

`shopify app deploy --allow-updates --version adfeed-ai-14 --message "Needs-attention-first App Home"`

### Task 5: Manual check

Hard refresh App Home: with prior quality report, first screen shows 要处理 N; feeds below; pipeline collapsed.
