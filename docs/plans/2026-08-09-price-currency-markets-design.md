# AdFeed AI — Price / Currency Alignment via Shopify Markets

**Date:** 2026-08-09  
**Status:** Approved — implementation started 2026-08-09 (see `2026-08-09-price-currency-markets.md`)  
**Related:** `2026-08-06-shopify-app-multi-platform-design.md`

---

## 1. Problem

Google Merchant Center (and similar channels) require:

> **Feed `price` + currency ≡ amount + currency shown on the product `link` landing page**
> (including structured data / JSON-LD when present).

AdFeed currently maps country → currency via `CURRENCY_MAP` and converts with `_convert_price` / `EXCHANGE_RATES`, treating stored amounts as USD. That breaks when:

- Store admin / storefront currency is **CNY** (or other) but Feed targets **US → USD**
- Shopify Markets serves **IP-based** currency while Googlebot often crawls from **US IPs**
- Feed amount is a private FX conversion that **never appears** on the landing page

Result: `Mismatched product price` / inconsistent currency — product disapproval (not usually instant ban; large persistent mismatches can escalate).

**Hard constraint:** No code path can disable Google’s crawl check. The product can only emit prices that match what the URL displays, or **block / warn** before export.

---

## 2. Product decision

| Rule | Behavior |
|------|----------|
| **Default market** | App defaults to **US (USD)**. |
| **Merchant action** | Whatever market they select, they must make the **storefront show that currency** in Shopify (manually). |
| **AdFeed** | Consistency check + pin `?currency=`; **block** on mismatch. No 入门/进阶 framing. |
| **Never** | Silent FX into submit feeds. |

---

## 3. Goals & non-goals

### Goals

- Merchants pick **platform × country**; AdFeed uses that country’s **buyer-visible** price/currency.
- Links in Feed force that currency on the storefront.
- Clear UX when the store cannot support the selected country (e.g. CNY-only shop generating Google-US).
- Reduce GMC price/currency disapprovals caused by AdFeed itself.

### Non-goals (this design)

- Changing Google / Meta / TikTok policy enforcement.
- Building a full currency hedging or B2B login-price system.
- Replacing Shopify Markets configuration UI (we deep-link / instruct; we don’t reimplement Markets admin).
- Guaranteeing Approve when shipping, website claiming, or other GMC setup is wrong.

---

## 4. User experience

### Generate flow (additions)

```
Select products
  → Select platforms (Google / Meta / TikTok)
  → Select markets/countries (US, DE, …)
  → Preflight: Markets readiness per country
       · Green: market exists, presentment price+currency OK
       · Red: no market / no presentment / storefront currency cannot match
  → Block Generate for red countries (default)
  → On success: durable Feed URL + sample row preview
       Feed price | currency | pinned landing link
```

### Merchant copy (examples)

- **Green:** “美国市场：USD 展示价可用。链接将带 `?currency=USD`。”
- **Red (CNY-only → US):** “店铺前台为 CNY，且未启用美国市场 USD 价。Google 会比对落地页价格，仅靠汇率换算无法过审。请在 Shopify Markets 启用美国并设置美元价后再生成。”
- **Same currency:** “店币与目标国一致（如 USD→US）。仍会钉 `?currency=`，避免爬虫 IP 切币导致误杀。”

### What merchants must do outside AdFeed

1. Enable the target country in **Shopify Markets** (or equivalent presentment).
2. Ensure buyers (and bots hitting the Feed link) see that market’s currency/amount.
3. Keep GMC **shipping** currency aligned with product currency for that country.
4. Landing pages publicly reachable (no password gate) for crawl checks.

One-line merchant rule:

> Feed 卖哪国，前台就要用哪国货币显示同一价格；AdFeed 不会把人民币「换汇」成谷歌认可的美元页。

---

## 5. Scenario matrix

| ID | Storefront / Markets | Feed target | AdFeed behavior |
|----|----------------------|-------------|-----------------|
| A | US page USD | Google-US | Use presentment USD; pin `?currency=USD` |
| B | DE page EUR | Google-DE | Use EUR; pin EUR / `/en-de/` if configured |
| C | CNY only, no US market | Google-US | **Block** + Markets guidance |
| D | Admin CNY, US Market USD | Google-US | Use **US presentment** USD, not admin CNY |
| E | Multi-market US/DE/UK | Multi feeds | Per-country price + currency + pinned link |
| F | Sale / compare-at | Any | `price` = current; `sale_price` if on sale and page shows it |
| G | Variant prices differ | Variant feed | Per-variant presentment; link includes `variant=` |
| H | Password / draft | Any | Preflight warn: crawl may fail |
| I | B2B / login prices | Any | Use **guest** presentment (what Google sees) |
| J | IP geolocation Markets | Localized feed | Pin currency or market URL so bot ≠ random IP currency |
| K | Same currency, wrong country shipping | — | Price OK; shipping check separate |

---

## 6. Architecture

### 6.1 Data flow

```
Shopify Admin / Markets API
  → resolve PresentmentPrice(country) per variant
  → store snapshot: amount, currency_code, market_id, synced_at
  → generate_feed(country):
       price/currency from snapshot (not _convert_price)
       link = base_url + variant + ?currency=CODE (+ market path if available)
  → preflight(country) before write
  → write XML/CSV
```

### 6.2 Components (logical)

| Component | Responsibility |
|-----------|----------------|
| `MarketPriceResolver` | Given shop + country + variant → presentment amount/currency; or error `NO_MARKET` / `NO_PRESENTMENT` |
| `FeedLinkBuilder` | Build final product URL with `variant`, `currency`, optional market prefix; no redirect chains |
| `GeneratePreflight` | Per selected country: green/red; block red by default |
| `FeedGenerator` | Consume resolved prices only; retire FX submit path |
| Store sync | Persist presentment fields alongside or instead of assuming `price_usd` |

### 6.3 Link pinning rules

1. Prefer **market-specific path/domain** from Shopify Markets when the shop uses subfolders/subdomains (`/en-us/products/...`).
2. Always append **`currency={ISO}`** matching Feed currency when Shopify supports it (idempotent if already present).
3. Include **`variant={id}`** for variant rows.
4. Submitted URL must be the **final** URL (no hop that drops currency or switches domain/currency).

### 6.4 Preflight policy (default)

| Result | Generate? |
|--------|-----------|
| All selected countries green | Yes |
| Any country red | **Block that country** (do not write that feed); other green countries may still generate |
| API/scopes missing for Markets | Red + “re-auth / grant Markets scopes” |

**Override (optional, later):** “Export anyway” with explicit checkbox and watermark in UI that GMC will likely disapprove — **off by default**, not in MVP unless product asks for it.

---

## 7. Changes vs current code (implementation hints)

| Area today | Target |
|------------|--------|
| `feed_generator.CURRENCY_MAP` + `_convert_price` + `EXCHANGE_RATES` for submit | Do not use for Feed `g:price`; resolve presentment instead |
| `price_usd` naming / assumption catalog is USD | Store `price_amount` + `currency_code` per market (or map country → presentment row) |
| Link from `store.site_url` only | `FeedLinkBuilder` + currency (and market path) |
| No generate-time currency gate | `GeneratePreflight` in App + `pipeline.generate_feed_for_store` |
| Sync via Admin REST `price` (shop currency) | Also fetch Markets / contextual pricing for each enabled feed country |

Exact Shopify API (GraphQL `contextualPricing`, Markets catalogs, etc.) is an implementation detail for the follow-up plan; design requirement is **buyer-visible price for that country**, not Admin home-currency alone.

---

## 8. Error handling & diagnostics

- Structured preflight codes: `NO_MARKET`, `CURRENCY_MISMATCH`, `MISSING_SCOPE`, `ZERO_PRICE`, `UNREACHABLE_HINT`
- Sample SKU in UI: open pinned link instructions + show Feed triple `(amount, currency, link)`
- Compliance diagnostic: extend price checks to compare Feed currency vs resolved market currency (not vs assumed USD)
- Logging: never log tokens; log country, currency, source=`markets|fallback_blocked`

---

## 9. Testing strategy

- Unit: link builder (`currency` query merge, variant, no double `?`)
- Unit: preflight matrix (A–K subset)
- Unit: generator refuses FX path when presentment missing
- Integration (mock Shopify): US presentment USD vs shop CNY admin price → Feed uses USD
- Regression: same-currency shop still generates; pins `?currency=`
- Manual GMC: after US Market enabled on test shop, price mismatch on currency should clear (shipping/other issues out of scope)

---

## 10. Rollout

1. Implement resolver + link builder + preflight behind clear behavior (no silent FX).
2. Migrate generate path for Google first; Meta/TikTok same price/link rules.
3. Document merchant checklist in App empty/red states.
4. Deprecate `_convert_price` for submit; keep or delete FX helpers only if preview needs them later.

---

## 11. Success criteria

- CNY-only test shop selecting Google-US → **blocked with actionable copy**, no USD FX feed written.
- Shop with US Market USD → Feed amount/currency match pinned `?currency=USD` page.
- Multi-country selection → independent feeds, each with its own presentment + pin.
- No reliance on AdFeed-internal FX for GMC approval path.

---

## 12. Open items (implementation plan)

- Exact Shopify GraphQL fields and required OAuth scopes for Markets/contextual pricing.
- Whether to cache presentment per sync job vs live fetch at generate.
- Market URL path discovery vs currency query only for MVP.
- Shipping currency alignment check (sister preflight, can be phase 2).

---

## 13. Summary

AdFeed will match competitor UX: **Markets presentment as price truth + automatic currency pinning on links + block generate when the storefront cannot match the Feed.** Internal exchange-rate conversion is not a valid Google approval strategy and must not be the default submit path.
