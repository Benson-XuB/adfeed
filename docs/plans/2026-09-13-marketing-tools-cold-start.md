# Marketing Tools Cold Start — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 用一批可搜索、免登录（或只读 OAuth）的小工具拉冷启动流量：补齐 Title Checker、加厚 Feed Checker、规划 Shopify 店检，并把 `/tools/` 收成「诊断 → waitlist」漏斗。

**Architecture:** 继续走营销站 `landing-page/tools/*` + FastAPI `phase0/adfeed/public_tools/*` 公共 API（不经 Shopify session）。与审核中的嵌入式 App **隔离**；可 `deploy-landing-only` / `deploy-from-local --backend-only`。规则诊断为主；「Fix with AI」只出**建议标题**，不写回店铺、不编假 GTIN/品牌。

**Tech Stack:** HTML/CSS/JS on `landing-page/`；FastAPI + 现有 `feed_checker` / `google_issues` / `google_ads_*`；waitlist CTA；nginx `/tools/*`。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**Related (already shipped — do not rebuild):**
- `docs/plans/2026-09-06-landing-feed-checker-gmc-tools.md` → Feed Checker + MC Issues
- `docs/plans/2026-09-08-tools-seo-copy.md` → SEO / guides
- Live: `/tools/feed-checker`, `/tools/google-issues`, `/tools/google-ads-monitor`

**Out of scope this week:** Shopify App UI、安检动画、真写 Feed、假 GTIN、把 Style 塞进 color、Ads 出价改写。

---

## 0. Product lock (next few days)

### 0.1 Funnel

```
Search / share
  → Tool (diagnose in <30s)
  → Plain-language report + “AdFeed can / cannot”
  → Get early access (waitlist, utm_source=tools&utm_medium=<tool>)
```

### 0.2 Inventory

| Tool | Status | This plan |
|------|--------|-----------|
| ② Feed Checker | Shipped | **Thicken** (counts, GTIN/price/availability soft checks) |
| ④ MC Disapproval | Shipped | Light CTA / hub copy only |
| Ads Monitor | Shipped | Hub copy fix (no old “developer token” story) |
| ① Title Checker | **Missing** | **Build first** |
| ③ Shopify → Google store check | **Missing** | Spec + spike only this week; full build if ①+② done early |

### 0.3 Field-contract guardrails (Title / AI)

- Diagnose missing **signals** (material / style / audience / color / size) — not “add more keywords for uniqueness”
- AI suggest = **one shorter shopping title suggestion**; never invent brand / GTIN / COGS
- No stacking color into title beyond what’s in the user’s paste
- Copy: shopping-card readable > attribute wall

### 0.4 Day map (suggested)

| Day | Focus |
|-----|--------|
| D1 | Title Checker API + page + tests + deploy |
| D2 | Feed Checker thicken + tools hub funnel |
| D3 | Shopify store-check spike / thin MVP **or** SEO guides for Title |
| D4+ | Polish conversion + measure waitlist `source=` |

---

## Task 1: Title Checker — backend rules (no AI yet)

**Files:**
- Create: `phase0/adfeed/public_tools/title_checker.py`
- Create: `phase0/tests/test_public_title_checker.py`
- Modify: `phase0/adfeed/public_tools/router.py`

**Step 1: Write failing tests**

```python
# phase0/tests/test_public_title_checker.py
from adfeed.public_tools.title_checker import analyze_title

def test_noisy_long_title_flags_improve():
    r = analyze_title("Women's Summer Dress Casual Loose New Arrival Free Shipping Hot Sale")
    assert r["ok"] is True
    assert r["verdict"] in ("improve", "ok", "weak")
    codes = {i["code"] for i in r["issues"]}
    assert "noisy_words" in codes or "too_long" in codes

def test_short_clean_title_ok_or_soft_gaps():
    r = analyze_title("Women's Linen Midi Dress Blue M")
    assert r["ok"] is True
    assert "suggested_title" in r  # may equal input if already fine
```

**Step 2: Run tests — expect FAIL**

```bash
cd phase0 && .venv/bin/pytest tests/test_public_title_checker.py -q
```

**Step 3: Implement `analyze_title(raw: str) -> dict`**

Return shape:

```python
{
  "ok": True,
  "input": "...",
  "verdict": "ok" | "improve" | "weak",  # weak = very short / empty signals
  "issues": [
    {"code": "too_long", "label": "...", "advice": "..."},
    {"code": "noisy_words", "label": "...", "advice": "..."},
    {"code": "missing_material", "label": "...", "advice": "..."},
    {"code": "missing_style", "label": "...", "advice": "..."},
    {"code": "missing_audience", "label": "...", "advice": "..."},
    {"code": "missing_color", "label": "...", "advice": "..."},
    {"code": "missing_size", "label": "...", "advice": "..."},
  ],
  "present": {"audience": True, "color": False, ...},
  "suggested_title": "...",  # rule-based strip noise + keep order; no LLM yet
  "disclaimer": "Suggestion only — do not invent brand or GTIN.",
}
```

Reuse noise patterns from `feed_checker.py` (`TITLE_NOISE_RE`) where possible; soft length ~70 chars (Shopping card).

**Step 4: Wire POST `/api/public/title-check`**

```python
class TitleCheckRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)

@router.post("/title-check")
async def title_check(body: TitleCheckRequest):
    return analyze_title(body.title.strip())
```

**Step 5: Tests pass + commit**

```bash
cd phase0 && .venv/bin/pytest tests/test_public_title_checker.py -q
git add phase0/adfeed/public_tools/title_checker.py phase0/adfeed/public_tools/router.py phase0/tests/test_public_title_checker.py
git commit -m "feat(tools): Google Shopping title checker API (rules)"
```

---

## Task 2: Title Checker — landing page + hub card

**Files:**
- Create: `landing-page/tools/title-checker.html`
- Create: `landing-page/tools/title-checker.js`
- Modify: `landing-page/tools/index.html`
- Modify: `landing-page/styles.css` (only if needed for shared tools classes)

**Step 1: Page shell (SEO)**

- URL: `/tools/title-checker`
- Title: `Google Shopping Title Checker — Free Title Fix Hints | AdFeed`
- H1: `Check Your Google Shopping Title`
- Lead: paste title → missing signals → optional shorter suggestion
- CTA: Get early access → `/#waitlist?utm_source=tools&utm_medium=title-checker`

**Step 2: UI**

- Textarea + **Check title**
- Verdict banner + issue list (“Missing: material / style / …”)
- **Suggested title** box (copy button)
- Button label **Suggest cleaner title** (rules). Optional later: **Improve with AI** → separate endpoint; same guardrails
- Link to Feed Checker + waitlist

**Step 3: JS calls** `POST /api/public/title-check` with `{ "title": "..." }`

**Step 4: Add card on `/tools/index.html` (first or second position)**

**Step 5: Deploy landing + restart API if needed; smoke on deltfu.com**

**Step 6: Commit**

```bash
git add landing-page/tools/title-checker.html landing-page/tools/title-checker.js landing-page/tools/index.html
git commit -m "feat(tools): title checker page for cold-start SEO"
```

---

## Task 3 (optional same day): Title “Fix with AI” — gated suggestion

Only if D1 rules ship and you want the button copy from the brainstorm.

**Files:**
- Modify: `phase0/adfeed/public_tools/title_checker.py`
- Modify: `phase0/adfeed/public_tools/router.py`
- Modify: `landing-page/tools/title-checker.js`

**Rules:**
- Prompt: shorten for Shopping card; keep facts present in input; **never invent** brand/GTIN/material not implied
- Cap tokens; timeout; fall back to rule `suggested_title` on failure
- Rate-limit by IP (simple in-memory or reuse existing patterns)
- Response field: `suggested_title_ai` + `source: "ai"|"rules"`

**Commit:** `feat(tools): optional AI title suggestion with no invented attributes`

---

## Task 4: Feed Checker — thicken report

**Files:**
- Modify: `phase0/adfeed/public_tools/feed_checker.py`
- Modify: `phase0/tests/test_public_feed_checker.py` (or create if thin)
- Modify: `landing-page/tools/feed-checker.html` / `.js` for summary counts

**Step 1: Summary shape users expect**

```text
1,284 products checked (capped at max_items)
73 potential issues found
```

Expose: `items_checked`, `items_capped`, `issue_total`, `buckets_summary`.

**Step 2: Add soft checks (warn, not fake fixes)**

| Code | Meaning |
|------|---------|
| `missing_gtin_and_no_identifier_exists` | Prefer “use compliant identifier-exists path” — **never** “generate GTIN” |
| `price_format` | Missing/odd price string |
| `availability_odd` | Empty / unknown availability |
| (defer) storefront price scrape mismatch | Needs Shopify URL tool |

**Step 3: UI** — big count line at top; keep sample rows ≤3 per bucket

**Step 4: Tests + commit**

```bash
git commit -m "feat(tools): richer feed checker counts and soft GTIN/price checks"
```

---

## Task 5: Tools hub funnel + copy cleanup

**Files:**
- Modify: `landing-page/tools/index.html`
- Modify: Ads monitor card text (drop obsolete developer-token line)
- Optionally: `landing-page/index.html` link “Free tools” prominence

**Copy structure:**
1. One H1: diagnose before you generate  
2. Ordered cards: Title → Feed → MC Issues → Ads Monitor  
3. Each card: pain → outcome → link  
4. Shared footer CTA waitlist

**Commit:** `fix(tools): hub order and cold-start funnel copy`

---

## Task 6: Shopify store checker — spike only (or thin MVP)

**Files:**
- Create: `docs/plans/spikes/2026-09-13-shopify-storefront-feed-check-spike.md`
- Optionally later: `phase0/adfeed/public_tools/shopify_store_check.py`

**Spike must answer:**
1. Can we use public `https://{shop}.myshopify.com/products.json` (pagination limits)?  
2. What we can infer without Admin API: title, vendor-as-dirty-brand, images, variants color/size, price  
3. What we **cannot**: real GTIN, GMC disapproval, private apps  
4. Abuse limits (rate, max pages)

**Thin MVP (only if spike green and D1–D2 done):**
- Input: `shop.myshopify.com`  
- Output: counts for missing brand signal / weak titles / no images / variant gaps  
- CTA waitlist `utm_medium=shopify-checker`  
- **No** Admin OAuth this week

**Commit spike doc even if MVP slips:** `docs(spike): shopify public products.json store check`

---

## Task 7: SEO guide stub for Title Checker

**Files:**
- Create: `landing-page/guides/google-shopping-title-examples.html` (short)
- Modify: `landing-page/guides/index.html` link

Link → `/tools/title-checker` → waitlist. Mirror tone of `2026-09-08-tools-seo-copy.md`.

**Commit:** `content(guides): shopping title examples → title checker`

---

## Verification checklist (before calling the week done)

- [ ] `/tools/title-checker` live; API returns verdict + issues + suggestion  
- [ ] No copy suggests inventing GTIN/brand  
- [ ] Feed checker shows **N checked / M issues**  
- [ ] `/tools/` lists Title + Feed + Issues + Ads in funnel order  
- [ ] Waitlist links carry `utm_source=tools&utm_medium=...`  
- [ ] Shopify App / App Store review binary untouched  
- [ ] `pytest` for title (+ feed if changed) green  

---

## Explicit non-goals

- Replacing App feed generator with marketing tools  
- Auto-install Shopify or write Merchant products  
- Ranking for “AI product title generator” spam SERPs with keyword stuffing  
- Blocking on Explorer Ads access for Title/Feed tools  

---

## Execution handoff

Plan saved to `docs/plans/2026-09-13-marketing-tools-cold-start.md`.

**Two execution options:**

1. **Subagent-Driven (this session)** — fresh subagent per task, review between tasks  
2. **Parallel Session** — new chat with executing-plans, start at Task 1  

Which approach?
