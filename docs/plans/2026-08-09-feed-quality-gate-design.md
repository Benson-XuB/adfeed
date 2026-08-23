# AdFeed — Generate-Time Feed Quality Gate (All Categories)

**Date:** 2026-08-09  
**Status:** Approved  
**Decisions:**
- Apparel/footwear/accessories with no size → auto-fill **`One Size`** (logged as auto-fix).
- **FATAL** rows still **enter the Feed**, but are flagged red in the generate report; merchant decides whether to upload to Google.

---

## 1. Goal

Before merchants upload to Google Merchant Center, AdFeed must:

1. **Auto-fix** safe, industry-standard gaps (e.g. One Size).
2. **Detect** issues across **all product types** (not apparel-only).
3. **Report** clearly: auto-fixed / warnings / fatals — so problems are not first seen in GMC.

Never silently FX-convert currency. Never invent prices or images.

---

## 2. Pipeline

```
Build feed rows
  → AutoFix (category-aware)
  → Diagnose (FATAL / WARN / INFO_AUTOFIX)
  → Write Feed (include FATAL rows)
  → Return report { autofixed[], warnings[], fatals[], checklist[] }
  → App shows three buckets + “upload at your own risk” if fatals > 0
```

---

## 3. Severity

| Level | Meaning | Feed | UI |
|-------|---------|------|-----|
| **AUTOFIX** | We filled a safe default | Included | Green/gray “已自动处理” |
| **WARN** | Limited / quality risk | Included | Yellow |
| **FATAL** | Likely disapproval if uploaded | **Still included** | Red — merchant choice |
| **BLOCK** (country) | Currency mismatch for market | Country feed not written | Existing currency preflight |

Currency country block remains separate from per-SKU FATAL.

---

## 4. Rule groups (all categories)

### 4.1 Universal

| Rule | AutoFix | Diagnose |
|------|---------|----------|
| Empty/zero price | — | FATAL |
| Bad/missing title | trim/promo strip if possible | FATAL if still bad |
| Missing description | short fallback from title+attrs | WARN if fallback |
| Missing brand | store default brand | AUTOFIX + note |
| Missing GTIN | identifier_exists=no | AUTOFIX/INFO |
| Missing GPC | matcher | WARN if low confidence / FATAL if empty after match |
| Missing image / non-http(s) | — | FATAL |
| Suspicious image CDN | — | WARN |
| Bad link | absolute URL + currency pin | FATAL if unusable |
| Availability | from inventory | — |
| Currency vs market | — | BLOCK country (existing) |

### 4.2 Apparel / footwear / accessories (GPC/path heuristics)

| Rule | AutoFix | Diagnose |
|------|---------|----------|
| Missing size | **`One Size`** | AUTOFIX |
| Missing color | resolve from variant/title/desc if possible | WARN/FATAL if still empty |
| Missing gender | heuristic / unisex | AUTOFIX or WARN |
| Missing age_group | default `adult` | AUTOFIX |

### 4.3 Other category hooks (extensible)

| Group | Examples | Behavior |
|-------|----------|----------|
| Electronics | color when multi-variant | WARN if color empty on colored variants |
| Beauty | shade/color | WARN if empty |
| Food/supplements | market-specific | WARN checklist, no fake nutrition |
| Furniture | shipping weight | WARN if missing |
| Books | ISBN/GTIN | WARN if missing |
| Generic hardgoods | universal only | — |

Category detection: GPC code/path + product_type keywords; unknown → universal rules only.

---

## 5. Report shape (API / job result)

```json
{
  "quality_report": {
    "total_rows": 152,
    "autofixed": [{ "sku": "...", "rule_id": "S01", "message": "已填 One Size" }],
    "warnings": [{ "sku": "...", "rule_id": "C02", "message": "...", "suggestion": "..." }],
    "fatals": [{ "sku": "...", "rule_id": "I01", "message": "主图为空", "suggestion": "..." }],
    "checklist": ["确认 GMC 目标国运费已配置", "上传后等待图片处理"]
  }
}
```

App: show counts + expandable lists; if `fatals.length > 0`, banner: “仍有高风险问题已写入 Feed，上传 Google 前请自行确认。”

---

## 6. Implementation phases

1. **P0:** `One Size` autofix + size missing diagnostic; wire report into `generate_feed_for_store`; return in job result; App banner/lists.
2. **P1:** Reuse/extend `compliance_diagnostic.py` on generate rows; brand/image/title/GPC into same report.
3. **P2:** Category-group WARN rules (beauty, electronics, …); store-external checklist.

---

## 7. Success criteria

- Boat socks (and any apparel without size) get `g:size=One Size` and appear under autofixed.
- Generate UI/API surfaces fatals without dropping those rows from XML.
- Currency mismatch still blocks country feed generation.
- Merchants can see issues **before** GMC “Missing size” / similar.
