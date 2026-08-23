# Price / Currency Markets Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Feed prices use buyer-visible currency (shop/Markets presentment), links pin `?currency=`, and generate preflight blocks country feeds when storefront cannot match — no internal FX on submit paths.

**Architecture:** Pure helpers (`FeedLinkBuilder`, `MarketPriceResolver`, `GeneratePreflight`) then wire into `pipeline.generate_feed_for_store`, `feed_generator.generate`, and `multi_platform_feeds`. MVP uses store `default_currency` + optional per-country presentment map; live Shopify Markets GraphQL is a follow-up behind the same resolver interface. FX helpers stay unused for feed submit.

**Tech Stack:** Python 3, pytest, existing `phase0/adfeed` store pipeline, urllib.parse for links.

**Design:** `docs/plans/2026-08-09-price-currency-markets-design.md`

---

### Task 1: FeedLinkBuilder (pin currency + variant)

**Files:**
- Create: `phase0/adfeed/feed_link.py`
- Test: `phase0/tests/test_feed_link.py`

**Step 1: Write the failing test**

```python
from adfeed.feed_link import build_product_link

def test_pins_currency_and_variant():
    url = build_product_link(
        "https://shop.example.com/products/dress",
        variant_id="123",
        currency="USD",
    )
    assert url.startswith("https://shop.example.com/products/dress?")
    assert "variant=123" in url
    assert "currency=USD" in url

def test_merges_existing_query_without_double_question():
    url = build_product_link(
        "https://shop.example.com/products/dress?utm_source=x",
        currency="EUR",
    )
    assert url.count("?") == 1
    assert "utm_source=x" in url
    assert "currency=EUR" in url

def test_overrides_existing_currency_param():
    url = build_product_link(
        "https://shop.example.com/products/dress?currency=CNY",
        currency="USD",
    )
    assert "currency=USD" in url
    assert "currency=CNY" not in url
```

**Step 2: Run test to verify it fails**

Run: `cd phase0 && python -m pytest tests/test_feed_link.py -v`  
Expected: FAIL (module missing)

**Step 3: Implement `build_product_link` in `feed_link.py`**

- Parse URL with `urllib.parse`
- Set/replace `currency`, optional `variant`
- Return normalized URL string

**Step 4: Run tests — expect PASS**

**Step 5: Commit** (only if user asked; otherwise skip until batch)

---

### Task 2: Country currency map + price resolve + preflight

**Files:**
- Create: `phase0/adfeed/market_pricing.py`
- Test: `phase0/tests/test_market_pricing.py`

**Step 1: Failing tests**

```python
from adfeed.market_pricing import (
    expected_currency_for_country,
    resolve_market_price,
    preflight_country,
    PreflightStatus,
)

def test_expected_currency():
    assert expected_currency_for_country("US") == "USD"
    assert expected_currency_for_country("DE") == "EUR"

def test_resolve_same_shop_currency_uses_amount_no_fx():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="USD",
        country="US",
        presentment=None,
    )
    assert r.ok
    assert r.amount == 199.0
    assert r.currency == "USD"
    assert r.source == "shop"

def test_resolve_presentment_overrides_shop_cny_for_us():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="CNY",
        country="US",
        presentment={"US": {"amount": 27.85, "currency": "USD"}},
    )
    assert r.ok
    assert r.amount == 27.85
    assert r.currency == "USD"
    assert r.source == "markets"

def test_resolve_mismatch_without_presentment_fails():
    r = resolve_market_price(
        amount=199.0,
        shop_currency="CNY",
        country="US",
        presentment=None,
    )
    assert not r.ok
    assert r.code == "CURRENCY_MISMATCH"

def test_preflight_blocks_cny_for_us():
    pf = preflight_country(shop_currency="CNY", country="US", sample_presentment=None)
    assert pf.status == PreflightStatus.RED
    assert pf.code == "CURRENCY_MISMATCH"

def test_preflight_green_when_currencies_align():
    pf = preflight_country(shop_currency="USD", country="US", sample_presentment=None)
    assert pf.status == PreflightStatus.GREEN
```

**Step 2: Run — expect FAIL**

**Step 3: Implement**

- `COUNTRY_CURRENCY` map (US→USD, DE/FR/ES/IT→EUR, …)
- `ResolvedPrice` dataclass: ok, amount, currency, source, code, message
- `resolve_market_price`: presentment for country wins; else if shop_currency == expected → shop amount; else fail (no FX)
- `preflight_country`: GREEN/RED + merchant-facing Chinese message for Markets setup
- Do **not** call `_convert_price` / exchange rates

**Step 4: Tests PASS**

---

### Task 3: Stop FX on Google feed row generation

**Files:**
- Modify: `phase0/adfeed/feed_generator.py` (`generate` path that builds products from DataFrame)
- Test: `phase0/tests/test_feed_price_no_fx.py`

**Step 1: Failing test**

Build a one-row DataFrame with `价格=199`, `currency=CNY` (or column `_feed_currency`), country `US`, assert output XML/dict uses `199.00 CNY` (or whatever row currency is) — **not** converted USD. Prefer asserting the internal product dict via a small helper or parsing XML `g:price`.

Safer API: if row has `_feed_currency` and numeric price, use those; if missing currency, use `expected_currency_for_country` only when shop path already validated — generator should take currency from row, never FX.

**Step 2: Change `generate()`** to:
- Read `row.get("_feed_currency")` or `row.get("currency")`
- Use `float(价格)` as amount **without** `_convert_price`
- If currency missing, fall back to `expected_currency_for_country(country)` (legacy) but **still no FX multiply**

**Step 3: Leave `_convert_price` deprecated** (comment + unused by `generate` / store path). `generate_from_memory` can be updated in same task or Task 5 for consistency.

**Step 4: Tests PASS**

---

### Task 4: Wire pipeline — preflight, resolve price, pin links

**Files:**
- Modify: `phase0/adfeed/pipeline.py` (`generate_feed_for_store`)
- Test: `phase0/tests/test_generate_preflight_wire.py` (unit-level with mocks if DB heavy; or test helpers used by pipeline)

**Behavior in `generate_feed_for_store`:**

For each `country`:
1. `pf = preflight_country(store.default_currency, country, presentment_hint)`
2. If RED → append to `blocked_countries` with message; **skip writing that country feed**; continue others
3. For each variant row:
   - `resolve_market_price(v.price, store.default_currency, country, presentment)`
   - If not ok → skip variant or skip country (prefer skip country if systemic)
   - Set `价格` = resolved amount, `_feed_currency` = resolved currency
   - `链接` = `build_product_link(product_url, variant=..., currency=resolved.currency)`
4. Return payload includes `blocked_countries: [{country, code, message}]` and only successful `feed_urls`

**Presentment MVP:** read optional JSON from variant/product if column exists later; for now `presentment=None` unless we add a thin dict on store (skip DB migration in MVP).

**Step: Tests** for “CNY store + US → blocked, no feed file”; “USD store + US → link has currency=USD”

---

### Task 5: Meta / TikTok — same no-FX + row currency

**Files:**
- Modify: `phase0/adfeed/multi_platform_feeds.py`
- Test: extend `test_feed_price_no_fx.py` or add `test_meta_feed_currency.py`

Remove `orig_price * rate` conversion; use row `_feed_currency` / price as pipeline already set.

---

### Task 6: API surface for preflight (optional but useful)

**Files:**
- Modify: `phase0/adfeed/api.py` — if generate endpoint exists, return `blocked_countries` in JSON
- Keep merchant message strings from `market_pricing.py`

---

### Task 7: Shopify Markets live fetch (phase 2 stub)

**Files:**
- Create: `phase0/adfeed/shopify_markets.py` with `fetch_contextual_pricing(...)` stub or GraphQL when `read_markets` available
- Modify: `phase0/adfeed/config.py` — document/add scope `read_markets` (do not break existing installs without migration note)
- **MVP:** interface only + TODO; resolver already accepts `presentment` dict so sync can fill later

**Out of MVP commit if time-boxed:** skip live API; document in plan as next PR.

---

### Task 8: Verification

Run:
```bash
cd phase0 && python -m pytest tests/test_feed_link.py tests/test_market_pricing.py tests/test_feed_price_no_fx.py tests/test_generate_preflight_wire.py -v
```

Manual: regenerate feed for CNY test store targeting US → expect block message, no bad USD FX file overwrite (or skip US).

---

## Commit strategy

User has not required per-task commits historically; implement then offer one commit for the feature + plan docs unless asked otherwise.

## Execution note

User requested plan **and** start coding in the same session → execute Tasks 1→5 (and 6 if quick); Task 7 stub only if time permits.
