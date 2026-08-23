# Variant Attrs + Scene Priority Implementation Plan

> **STATUS: MOSTLY DONE** — scene 有则加 + `variant_attributes` 已落地。  
> **勿再据此加** `title_guard` 出口叠层。标题/色字段后续以 `2026-08-14-feed-field-contract.md` 减层为准。  

> **For Claude:** Do not re-run as greenfield. Remaining work is field-contract 减层, not more polish layers.

**Goal:** Implement remaining design-diff work: title scene priority 「有则加」, and `VariantAttributeCleaner` P0 (color/size/size_system/size_type) while keeping Multicolor fallback and already-fixed real Shopify `?variant=` IDs.

**Architecture:** Keep `title_optimizer` formulas; only change priority text in EN (and mirror in DE/FR/ES/IT lightly). Add `variant_attributes.py` for per-variant clean → wire in `pipeline.generate_feed_for_store` before `process_feed_rows`. `feed_quality` remains safety net; never overwrite real colors with Multicolor; never use Default.

**Tech Stack:** Python 3, pytest, existing `attribute_normalizer` / `feed_quality` / `feed_generator`

**Design:** `docs/plans/2026-08-11-title-keep-variant-attrs-design-diff.md`

**Already done (do not redo):**
- `resolve_shopify_variant_id` + pipeline passes `shopify_variant_id` into links
- VA04 warn + App banner when missing numeric ID

**Commit policy:** Skip commits unless user asks.

---

### Task 1: Title prompt — scene 「有则加」

**Files:**
- Modify: `phase0/adfeed/title_optimizer.py` (`_PROMPT_EN` primarily; mirror priority lines in DE/FR/ES/IT)
- Test: `phase0/tests/test_title_scene_priority_prompt.py`

**Step 1: Failing test**

```python
from adfeed.title_optimizer import _PROMPT_EN, _build_prompt

def test_en_prompt_scene_is_optional_not_number_one():
    assert "Scene words are the #1 priority" not in _PROMPT_EN
    assert "有则加" in _PROMPT_EN or "add scene only if it fits" in _PROMPT_EN.lower() or "SCENE is optional" in _PROMPT_EN
    # Priority order must drop scene before color when tight
    assert "CORE CATEGORY" in _PROMPT_EN
    low = _PROMPT_EN.lower()
    assert "drop" in low and "scene" in low
```

Adjust assertions to match the exact English wording you implement (see Step 3).

**Step 2:** Run test — expect FAIL

**Step 3: Edit `_PROMPT_EN`**

Replace:
- `Scene words are the #1 priority`
- `DROP secondary attributes (color, material first) — KEEP the scene intact`
- `Priority hierarchy: CORE CATEGORY > SCENE WORDS > Core Function > Color > Material`

With:
- Scene is **optional** (有则加): include `for [Scene]` only if it fits completely
- If over budget: **drop scene first**, then color/material
- Priority: `CORE CATEGORY > Core Function > Color/Material > SCENE (optional)`

Keep golden-30 and front_70 ≤66. Mirror the same priority intent in DE/FR/ES/IT (short edit).

**Step 4:** Tests PASS

**Step 5:** Skip commit unless asked

---

### Task 2: `clean_variant_attributes` pure helper (P0 rules)

**Files:**
- Create: `phase0/adfeed/variant_attributes.py`
- Test: `phase0/tests/test_variant_attributes.py`

**Step 1: Failing tests**

```python
from adfeed.variant_attributes import clean_variant_attributes

def test_strips_noise_and_maps_color_size():
    out = clean_variant_attributes(
        shopify_variant_id="41575567491130",
        color_raw="黑色 现货",
        size_raw="升级款 M",
        title="Women Cotton Tee",
        description="",
        gpc_path="Apparel & Accessories > Clothing",
    )
    assert out["shopify_variant_id"] == "41575567491130"
    assert out["g_color"] == "Black"
    assert out["g_size"] == "M"
    assert out["g_size_system"] == "US"
    assert out["g_size_type"] == "Regular"

def test_empty_color_apparel_multicolor_not_default():
    out = clean_variant_attributes(
        shopify_variant_id="1",
        color_raw="",
        size_raw="",
        title="Boat Socks",
        description="no color words",
        gpc_path="Apparel > Socks",
        extract_color_fn=lambda t, d: "Multicolor",  # inject; no live LLM
    )
    assert out["g_color"] == "Multicolor"
    assert out["g_size"] == "One Size"
    assert out["g_size_system"] == "US"

def test_non_apparel_skips_size_system():
    out = clean_variant_attributes(
        shopify_variant_id="2",
        color_raw="Black",
        size_raw="",
        title="USB Cable",
        description="",
        gpc_path="Electronics > Cables",
    )
    assert out["g_color"] == "Black"
    assert out.get("g_size_system") in ("", None)
    assert out.get("g_size_type") in ("", None)
```

**Step 2:** FAIL

**Step 3: Implement** using existing `normalize_color` / `resolve_gmc_color` / size maps / `is_apparel_like` from `feed_quality`. Noise tokens: 现货、升级款、新款、爆款、包邮…

**Step 4:** PASS

**Step 5:** Skip commit

---

### Task 3: Emit `size_system` / `size_type` in Google XML

**Files:**
- Modify: `phase0/adfeed/feed_generator.py` (ensure tags written when present on row)
- Test: small unit on row→xml or existing generator test

**Step 1:** Assert XML contains `<g:size_system>US</g:size_system>` and `<g:size_type>Regular</g:size_type>` when row has them.

**Step 2–4:** Wire fields from Chinese/English row keys (`size_system`, `size_type` or 约定键) into template / product dict.

**Step 5:** Skip commit

---

### Task 4: Wire cleaner into `generate_feed_for_store`

**Files:**
- Modify: `phase0/adfeed/pipeline.py` (where color/size set on each variant row)
- Test: `phase0/tests/test_pipeline_variant_attrs_wire.py` (monkeypatch cleaner or call with mock variant dict)

**Behavior:**
1. After building raw color/size from `v_data`, call `clean_variant_attributes(...)`.
2. Write cleaned values into row (`颜色`/`尺码`/`size_system`/`size_type`).
3. Keep existing `resolve_shopify_variant_id` for links (already done).
4. `process_feed_rows` still runs after — must not clobber real Black with Multicolor.

**Step 5:** Skip commit

---

### Task 5: Quality report events VA01–VA03

**Files:**
- Modify: `variant_attributes.py` and/or pipeline to append `QualityEvent`s
- Extend tests

| Rule | When |
|------|------|
| VA01 | color cleaned / Multicolor fallback |
| VA02 | size cleaned / One Size |
| VA03 | size_system/type filled |

Merge into `quality_report` like VA04.

---

### Task 6: Verification

```bash
cd phase0 && .venv/bin/python3 -m pytest \
  tests/test_feed_link.py \
  tests/test_title_scene_priority_prompt.py \
  tests/test_variant_attributes.py \
  tests/test_feed_quality.py \
  tests/test_sensitive_compliance.py \
  -v
```

Optional: regenerate store US feed; spot-check `size_system`/`size_type` and titles less scene-forced.

---

## Out of scope

- Replacing title formula with screenshot Role
- Color Default
- Fake variant IDs
- P1 whole-product LLM variant JSON array
