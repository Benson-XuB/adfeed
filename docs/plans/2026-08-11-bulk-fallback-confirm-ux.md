# Bulk Fallback Confirm UX — Implementation Plan

> **For Claude:** Implement task-by-task; skip commits unless user asks.

**Goal:** After generate, let merchants batch-fix Multicolor / One Size autofills via Magic Bar on HomePage (existing Polaris section), persist to `product_variants`, regenerate Feed, return fresh `quality_report`.

**Architecture:** `POST /api/app/quality/bulk_patch` (session store) → update variants by SKU → `generate_feed_for_store` (no re-optimize) → return feeds + quality_report. App extends quality section with buckets + select + Magic Bar.

**Design notes:** Requirements inventory §4.3–4.4; color LLM+Multicolor already backend; this is UX step ③ only. In-page Magic Bar (not full right drawer).

---

### Task 1: store_db get/update by SKU

- `get_variant_by_sku_for_store(store_id, sku)`
- `update_variant_attrs_for_store(store_id, sku, color=None, size=None)` — preserve other columns
- `apply_variant_attr_patches(store_id, patches)` → `{updated, missing}`

### Task 2: API `POST /api/app/quality/bulk_patch`

Body:
```json
{
  "patches": [{"sku": "...", "color": "Black"}, {"sku": "...", "size": "One Size"}],
  "platforms": ["google"],
  "languages": ["US"],
  "regenerate": true
}
```

- Auth: `require_store`
- Sync regenerate (no job/quota burn — attrs already optimized)
- Return `{ updated, missing, feeds, quality_report, message }`

### Task 3: products.ts `bulkPatchVariantAttrs`

### Task 4: HomePage

- Buckets from autofixed: Multicolor (`after`/`C01`/`VA01`), One Size (`S01`/`VA02`)
- Checkbox select per bucket + select-all
- Magic Bar when selection nonempty:
  - color text +「应用颜色」
  -「一键 One Size」
  - optional size text +「应用尺码」
- On success: refresh `qualityReport` + feeds; clear selection

### Task 5: Tests

- store_db patch unit
- API/helper smoke without Shopify
- optional UI not unit-tested
