# Shopping Title Quality — World-Formula Design

Field contract: `docs/plans/2026-08-14-feed-field-contract.md`  
North Star: `docs/plans/2026-08-12-mvp-north-star.md`

**Date:** 2026-08-15  
**Status:** APPROVED  
**Authority:** Google Merchant apparel title tips + industry apparel template; adapted for weak-brand 1688→Shopify feeds.

---

## 1. Verdict

High-quality Shopping titles are **attribute orchestration**, not prose.  
World pattern: `[Brand?] + Gender + Product Type + searchable attrs + Color + Size`.  
Our shop often has **weak brand** → do not force brand first; lead with gender + type + ≤2 searchable attrs; renderer appends this-row color/size.

## 2. Target formula (US apparel)

```text
[Women's/Men's] [Plus Size?] [Attr1] [Attr2] [Exact product type]
→ render: , {color}, Size {size}
```

- Length preference: slightly longer OK (~80–110 after render); hard cap 150.
- Attr budget: **≤2 searchable selling points**; **pattern/print takes priority** for one slot when present.
- Searchable material may take one slot: Denim / Leather / Silk / Cashmere / Merino / Cotton (alone).
- Default fabric wall never: Polyester, Spandex, Nylon-Spandex Blend, PU dump.
- Never: Closure / Fit Type / `•` / `|` / size ranges / supplier brand.

### Golden examples (acceptance)

| SKU type | Target shape |
|----------|----------------|
| Jeans | `Women's High Waist Stretch Jeans, Blue, Size L` |
| Floral dress | `Women's Floral Sleeveless Dress, Apricot, Size 2XL` |
| Jacket | `Women's Lace V-Neck Jacket, Black, Size L` |

## 3. Owners (field contract)

| Layer | Owner | May do | Must not |
|-------|--------|--------|----------|
| Skeleton | `title_optimizer` (prompt + premise) | Write gender + ≤2 attrs + type | Dump Closure/Fit/fabric wall/scenes essay |
| Sanitize | `title_guard.sanitize_shopping_title` | Strip banned junk leaking from old assets | Insert new selling points / floral / Plus |
| Render | `polish_feed_title` / `_enhance_title` | Append this-row color + size once | Mid-insert attributes |

## 4. Out of scope

- DE/FR/ES/IT prompt full rewrite (same bans can land later).
- Inventing brand / GTIN.
- Exit-layer “smart pick 2 attrs and stitch”.
