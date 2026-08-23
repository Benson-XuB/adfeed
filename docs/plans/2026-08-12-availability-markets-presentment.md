# Continue HQ Feed — Availability + Markets Presentment

> **For Claude:** Implement; skip commits unless asked.

**Goal:** (1) Feed `availability` only `in_stock`|`out_of_stock`. (2) Live Shopify `contextualPricing` for target country → unlock CNY shops with US Market USD.

**Architecture:** Fix `feed_generator` binary availability. Implement `shopify_markets.fetch_contextual_pricing` via Admin GraphQL `nodes`+`contextualPricing`; wire in `pipeline.generate_feed_for_store` into preflight + per-variant `presentment`.

---

### Task 1: Binary availability + test
### Task 2: Markets fetch + unit tests (mocked HTTP)
### Task 3: Pipeline wire + preflight sample
### Task 4: Verify pytest
