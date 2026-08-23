# High-Quality Feed Engine Implementation Plan

> **STATUS: MOSTLY DONE (2026-08-14)** — 勿机械重跑全文。  
> **纠偏：** 后续改动服从 `2026-08-14-feed-field-contract.md`（禁止出口打补丁；S7 去水印已废，主图自选见 image-picker）。  
> **未完成且允许的下一程：** 标题减层、color/pattern 分家、App 广告品牌确认 —— 见字段合同 §5。  

> **For Claude:** Do **not** re-implement completed tasks. New Feed work = field-contract 减层 only.

**Goal:** Make generate-time Google feeds approval-ready: complete attributes + no-barcode channel, sensitive-word soften/`adult`, and clean main images — with an explainable quality report (minimal UX).

**Architecture:** Extend existing `feed_quality` / `attribute_normalizer` / `title_optimizer` / `image_processor` / `pipeline.generate_feed_for_store`. Add a dedicated `sensitive_compliance` module (lexicon + adult). Keep TDD; wire report fields (`light`, `before`/`after`, title compare) into API + thin App Home UI. Dynamic Feed URL and big drawer UX are **out of scope**.

**Tech Stack:** Python 3, pytest, existing DashScope/OpenAI LLM, wanx image edit, React App Home (`HomePage.jsx`)

**Design:** `docs/plans/2026-08-10-high-quality-feed-engine-design.md`

**Reuse (do not rewrite):**
- `phase0/adfeed/feed_quality.py` — One Size + age_group + report skeleton
- `phase0/adfeed/attribute_normalizer.py` — `resolve_gmc_color`, SIZE_MAP → One Size
- `phase0/adfeed/dirty_word_filter.py` — ecommerce junk words (≠ adult/sensitive)
- `phase0/adfeed/title_optimizer.py` — AI titles
- `phase0/adfeed/image_processor.py` — `remove_watermark` / `process_product_image`
- `phase0/adfeed/pipeline.py` — already calls `process_feed_rows`, optional watermarks

**Commit policy:** Skip git commits unless the user explicitly asks.

---

## Task 1: QualityReport contract — `light` + before/after

**Files:**
- Modify: `phase0/adfeed/feed_quality.py`
- Test: `phase0/tests/test_feed_quality.py`

**Step 1: Failing tests**

```python
from adfeed.feed_quality import QualityEvent, QualityReport, traffic_light

def test_traffic_light_red_on_fatal():
    r = QualityReport(fatals=[QualityEvent("FATAL", "I01", "g:image_link", "x", "no image")])
    assert traffic_light(r) == "red"

def test_traffic_light_yellow_on_autofix_only():
    r = QualityReport(autofixed=[QualityEvent("AUTOFIX", "S01", "g:size", "x", "One Size")])
    assert traffic_light(r) == "yellow"

def test_traffic_light_green_when_clean():
    assert traffic_light(QualityReport(total_rows=1)) == "green"

def test_to_dict_includes_light_and_before_after():
    ev = QualityEvent("AUTOFIX", "S01", "g:size", "sku1", "filled",
                      suggestion="", before="", after="One Size")
    d = QualityReport(autofixed=[ev], total_rows=1).to_dict()
    assert d["light"] == "yellow"
    assert d["autofixed"][0]["after"] == "One Size"
```

**Step 2:** `cd phase0 && python -m pytest tests/test_feed_quality.py::test_traffic_light_red_on_fatal -v`  
Expected: FAIL (missing symbols)

**Step 3: Implement**

- Add optional `before: str = ""`, `after: str = ""` on `QualityEvent`
- Add `traffic_light(report) -> "green"|"yellow"|"red"`
- `to_dict()` includes `light` + serialize before/after
- Update One Size autofix to set `before=""`, `after="One Size"`

**Step 4:** Run full `tests/test_feed_quality.py` — PASS

**Step 5:** Skip commit unless asked

---

## Task 2: S1a — condition / gender / OSFA normalize / no-barcode brand

**Files:**
- Modify: `phase0/adfeed/feed_quality.py`
- Modify: `phase0/adfeed/pipeline.py` (brand resolver if needed)
- Test: `phase0/tests/test_feed_quality.py`
- Optional helper: `phase0/adfeed/brand_resolver.py` (only if pipeline brand logic is messy)

**Step 1: Failing tests**

```python
from adfeed.feed_quality import apply_row_autofixes, process_feed_rows

def test_condition_default_new():
    row = {"SKU": "a", "优化后标题": "Cotton Tee", "GPC路径": "Apparel > Shirts",
           "尺码": "M", "颜色": "Black", "价格": 10,
           "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a"}
    apply_row_autofixes(row)
    assert row.get("condition") == "new"

def test_gender_default_unisex_apparel():
    row = {"SKU": "a", "优化后标题": "Cotton Tee", "GPC路径": "Apparel > Shirts",
           "尺码": "M", "颜色": "Black"}
    apply_row_autofixes(row)
    assert row.get("gender") in ("unisex", "female", "male")

def test_osfa_aliases_normalize_to_one_size():
    row = {"SKU": "a", "优化后标题": "Socks", "GPC路径": "Apparel > Socks", "尺码": "OSFA"}
    apply_row_autofixes(row)
    assert row["尺码"] == "One Size"

def test_no_gtin_sets_identifier_exists_false():
    row = {
        "SKU": "a", "优化后标题": "Widget", "GPC路径": "Hardware",
        "价格": 5, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/a",
        "gtin": "", "identifier_exists": "",
        "brand": "",
    }
    events = apply_row_autofixes(row, brand_fallback="My Store")
    assert str(row.get("identifier_exists")).lower() in ("false", "no")
    assert row.get("brand") == "My Store"
    assert any(e.rule_id == "ID01" for e in events)
    assert "无码" in events[0].message or "identifier" in events[0].message.lower() or "条码" in events[0].message
```

**Step 2:** Run tests — expect FAIL

**Step 3: Implement in `apply_row_autofixes`**

| Rule | Behavior |
|------|----------|
| S03 | empty `condition` → `new` |
| S04 | apparel + empty `gender` → infer or `unisex` |
| S05 | size in `{OSFA, osfa, Free Size, 均码, 0SFA}` → `One Size` |
| ID01 | no GTIN → `identifier_exists=false` (or `no` if feed writer expects that — **match `feed_generator` / XML writer existing convention**), set brand from `brand_fallback` if empty |
| ID02 | if brand contains `myshopify.com` → replace with `brand_fallback` + WARN/AUTOFIX |

Signature: allow optional `brand_fallback: str = ""`.  
`process_feed_rows(rows, brand_fallback=...)` pass-through.

Wire `pipeline.generate_feed_for_store` to pass resolved brand (existing `_resolve_store_brand` ~line 1044 — extend: prefer custom domain / shop name, never `*.myshopify.com`).

**Step 4:** Tests PASS; spot-check XML/`identifier_exists` field name against `feed_generator.py`

**Step 5:** Skip commit

---

## Task 3: S1b — apparel color: variant → dict/LLM → Multicolor (autofill, not only WARN)

**Files:**
- Create: `phase0/adfeed/color_extract.py` (LLM extract helper)
- Modify: `phase0/adfeed/feed_quality.py` or call from `pipeline` before `process_feed_rows`
- Modify: `phase0/adfeed/attribute_normalizer.py` only if shared helpers needed
- Test: `phase0/tests/test_color_extract.py`, extend `test_feed_quality.py`

**Step 1: Failing tests**

```python
from adfeed.color_extract import extract_color_from_text

def test_extract_returns_black_from_chinese(monkeypatch):
    def fake_llm(prompt):
        return "Black"
    monkeypatch.setattr("adfeed.color_extract._llm_color", fake_llm)
    assert extract_color_from_text("法式连衣裙 黑色 V领", "") == "Black"

def test_extract_multicolor_when_none(monkeypatch):
    monkeypatch.setattr("adfeed.color_extract._llm_color", lambda p: "Multicolor")
    assert extract_color_from_text("USB cable 2m", "") == "Multicolor"
```

```python
# in test_feed_quality or pipeline unit
def test_apparel_empty_color_gets_multicolor_autofix(monkeypatch):
    monkeypatch.setattr(
        "adfeed.color_extract.extract_color_from_text",
        lambda t, d: "Multicolor",
    )
    row = {
        "SKU": "d1", "优化后标题": "Summer Dress", "描述": "法式碎花裙",
        "GPC路径": "Apparel > Dresses", "尺码": "M", "颜色": "",
        "价格": 20, "图片链接": "https://x/a.jpg", "链接": "https://s.com/p/d",
    }
    from adfeed.feed_quality import enrich_and_autofix_row
    events = enrich_and_autofix_row(row)
    assert row["颜色"] == "Multicolor"
    assert any(e.rule_id == "C01" for e in events)
```

**Step 2:** FAIL then implement

**Step 3: `color_extract.py`**

- Prompt: analyze title+HTML/text description; Chinese colors → English; if none return exactly `Multicolor`
- Use existing OpenAI/DashScope client pattern from `title_optimizer` (small max tokens)
- `enrich_and_autofix_row(row)` order:
  1. If apparel and color empty: try `resolve_gmc_color` on raw / description listed colors (**no LLM**)
  2. If still empty: LLM extract (batch later; MVP per-row ok with cache by title hash)
  3. If still empty or Multicolor from LLM: set `Multicolor`, AUTOFIX C01 (yellow)
  4. If real color found: AUTOFIX C02 “从文案提取颜色 → Black”
- Never overwrite a good variant color with Multicolor

**Step 4:** Prefer calling enrich in `process_feed_rows` so all generate paths get it. For LLM cost in tests, always monkeypatch.

**Step 5:** Skip commit

---

## Task 4: S1c — title compare payload (reuse optimizer)

**Files:**
- Modify: `phase0/adfeed/pipeline.py` (or feed row builder) to attach `original_title` / keep `标题` vs `优化后标题`
- Modify: `phase0/adfeed/api.py` job result shape if needed
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx`
- Test: `phase0/tests/test_title_compare_payload.py` (unit on helper)

**Step 1: Failing test**

```python
from adfeed.feed_quality import build_title_compare_samples

def test_title_compare_samples():
    rows = [{
        "SKU": "1",
        "标题": "2026跨境新款女装法式连衣裙",
        "优化后标题": "eprolo French Vintage Dress for Women - Red, One Size",
    }]
    samples = build_title_compare_samples(rows, limit=5)
    assert samples[0]["before"] == "2026跨境新款女装法式连衣裙"
    assert "French" in samples[0]["after"]
```

**Step 2–3:** Implement `build_title_compare_samples`; merge into `quality_report["title_compare"]` in pipeline after rows built.  
App: show up to 5 before/after pairs under quality section.

**Note:** Title AI already runs in pipeline — do **not** rewrite `title_optimizer` prompts unless a test shop sample still outputs Chinese junk; then a small follow-up task.

**Step 4:** PASS + manual App glance

**Step 5:** Skip commit

---

## Task 5: S6a — sensitive lexicon soften + `adult=yes`

**Files:**
- Create: `phase0/adfeed/sensitive_compliance.py`
- Create: `phase0/adfeed/data/sensitive_lexicon.json` (or inline dict in py for MVP)
- Modify: `phase0/adfeed/feed_quality.py` or `pipeline.py` to run **after** title optimize, **before** write
- Test: `phase0/tests/test_sensitive_compliance.py`

**Step 1: Failing tests**

```python
from adfeed.sensitive_compliance import apply_sensitive_compliance

def test_soften_tactical_knife():
    row = {
        "SKU": "k1",
        "优化后标题": "Tactical Combat Knife for Self Defense",
        "描述": "tactical combat knife",
    }
    events = apply_sensitive_compliance(row)
    title = row["优化后标题"].lower()
    assert "combat" not in title
    assert "camping" in title or "outdoor" in title or "tool" in title
    assert any(e.rule_id.startswith("SEN") for e in events)

def test_lingerie_forces_adult():
    row = {
        "SKU": "u1",
        "优化后标题": "Sexy Lace Lingerie Set for Women",
        "描述": "sexy lingerie",
        "GPC路径": "Apparel > Underwear",
    }
    events = apply_sensitive_compliance(row)
    assert str(row.get("adult")).lower() in ("yes", "true")
    assert any(e.rule_id == "AD01" for e in events)
```

**Step 2:** FAIL

**Step 3: Implement**

- Lexicon entries: `{match: regex/str, replace_title?: str, replace_desc?: str, force_adult?: bool, severity: soft|adult|fatal}`
- Seed: tactical/combat knife → Outdoor Camping Tool; lingerie/sexy underwear → force adult; massage gun adult-leaning phrases → soft or adult per table
- Mutate title/description; set `adult=yes` on row (ensure `feed_generator` emits `g:adult`)
- Return `QualityEvent` with before/after
- Integrate into `process_feed_rows` **or** pipeline loop after autofix; append events to report

**Verify:** grep `adult` in `feed_generator.py` / `multi_platform_feeds.py`; add tag if missing.

**Step 4:** PASS

**Step 5:** Skip commit

---

## Task 6: S6b (optional same PR) — LLM soften fallback

**Files:**
- Modify: `phase0/adfeed/sensitive_compliance.py`
- Test: monkeypatched LLM path

Only if lexicon miss rate is high on sample catalog. Prompt: rewrite to Google-shopping-safe outdoor/apparel wording; never invent medical claims. Skip if timeboxed — mark TODO in module docstring.

---

## Task 7: S7a — wire image clean into store generate + report

**Files:**
- Modify: `phase0/adfeed/pipeline.py` (`generate_feed_for_store`)
- Modify: `phase0/adfeed/api.py` — default `remove_watermarks=True` for store generate (or new `clean_images=True`)
- Modify: `phase0/adfeed/image_processor.py` if need `try_clean_main_image` wrapper returning `{ok, url, reason}`
- Test: `phase0/tests/test_image_clean_report.py`

**Step 1: Failing test**

```python
from adfeed.image_processor import classify_image_risk

def test_alicdn_flagged_risky():
    assert classify_image_risk("https://cbu01.alicdn.com/img/foo.jpg")["risky"] is True

def test_shopify_cdn_not_auto_risky():
    assert classify_image_risk("https://cdn.shopify.com/s/files/1/x/a.jpg")["risky"] is False
```

**Step 2–3:**

- `classify_image_risk(url)` — domain heuristics (alicdn, 1688, watermark query patterns)
- In generate path: if risky or `clean_images`: call `process_product_image` / `remove_watermark`; on success replace `图片链接` + AUTOFIX IMG01; on failure WARN IMG02 keep original
- Cap: e.g. max N images per job (config) to control cost; rest WARN “跳过图片处理（配额）”
- Do not FATAL on clean failure

**Step 4:** Unit tests PASS; optional live API test behind env flag (do not require in CI)

**Step 5:** Skip commit

---

## Task 8: App Home — light + optimization log + title compare + highlight table (minimal)

**Files:**
- Modify: `phase0/add-feed-ai/extensions/app-home/src/pages/HomePage.jsx`
- Possibly: `phase0/add-feed-ai/shared/models/products.ts` if typed

**Step 1:** Manual checklist (no Jest required if project has none)

UI requirements:
1. Show traffic light text: 绿/黄/红 from `quality_report.light`
2. Summary line: autofixed / warnings / fatals counts (already partially there)
3. Expandable log: first 20 autofixed with message (邀功文案可见)
4. Title compare section from `quality_report.title_compare`
5. “高亮微调” table: rows where autofix touched size/color/adult — **read-only first**; edit+save can be Task 8b if time permits (PATCH API may not exist — if no API, show read-only + “请在 Shopify 改后重新生成”)

**Step 2:** If edit API missing, document follow-up; do not block S1/S6/S7 backend.

**Step 3:** Skip commit

---

## Task 9: End-to-end verification

**Commands:**

```bash
cd phase0
python -m pytest tests/test_feed_quality.py tests/test_color_extract.py tests/test_sensitive_compliance.py tests/test_image_clean_report.py tests/test_title_compare_payload.py tests/test_feed_link.py tests/test_market_pricing.py -v
```

**Manual (test shop `9445344a-…` if token available):**
1. Generate US feed
2. Spot-check apparel: `g:size=One Size` where empty; color non-empty
3. Spot-check no GTIN: `identifier_exists` false + brand not myshopify
4. If knife/lingerie sample exists: softened title / adult
5. quality_report in job result has `light` + lists

**Success = design §10 acceptance.**

---

## Out of scope (do not implement in this plan)

- Dynamic Feed URL as primary delivery
- 安检舱 animation, Magic Bar drawer
- Full OCR Chinese detection (S7b)
- Lifestyle scene generation
- B2B / 1688 factory filter / short video

---

## Suggested execution order

1 → 2 → 3 → 5 → 7 → 4 → 8 → 9 → (6 optional)

S6 before S7 is fine; title compare UI can trail backend.
