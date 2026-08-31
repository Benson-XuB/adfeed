# Google API Push Dual Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** On an isolated branch, push AdFeed canonical product rows to Google via Merchant API `productInputs`, keep XML as escape hatch, and retain read-loop issues — without touching App Store review production.

**Architecture:** Reuse quality-engine rows from the existing feed pipeline; map to `ProductInput`; concurrent insert/patch against an API `dataSource`; gate with `GOOGLE_PUSH_ENABLED`; UI CTA only「推送到 Google（沙盒）」. XML generation stays for regression/escape.

**Tech Stack:** FastAPI, `store_db` SQLite, httpx, existing `platforms/google/oauth.py`, Merchant API Products (`productInputs`), pytest + mock clients.

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Design: docs/plans/2026-08-31-google-api-push-dual-export-design.md
```

**Hard constraints:**
- Do NOT change production `shopify.app.toml`, privacy, listing, or deploy review App.
- Do NOT invent GTIN / brand / dirty color.
- Do NOT use Content API `custombatch` — use Merchant `productInputs.*`.
- Do NOT remove Google XML generation.

---

### Task 1: Schema — dataSource + push runs

**Files:**
- Modify: `phase0/adfeed/store_db.py` (schema + helpers)
- Test: `phase0/tests/test_google_push_schema.py`

**Step 1: Write the failing test**

```python
def test_google_push_tables_and_datasource(tmp_path, monkeypatch):
    # init store schema on temp db
    # upsert merchant with data_source_name
    # insert push_run + push_item; fetch by store_id
    assert row["data_source_name"].startswith("accounts/")
    assert items[0]["offer_id"] == "SKU-1"
```

**Step 2: Run test to verify it fails**

Run: `cd phase0 && .venv/bin/pytest tests/test_google_push_schema.py -v`  
Expected: FAIL (missing tables/helpers)

**Step 3: Minimal schema**

- Add column `data_source_name` on `google_merchant_accounts` (migration-safe ALTER).
- Tables `google_push_runs`, `google_push_items`.
- Helpers: `set_merchant_data_source`, `create_push_run`, `add_push_item`, `finish_push_run`, `list_push_items`.

**Step 4: Run test — PASS**

**Step 5: Commit** (only if user asked to commit)

```bash
git add phase0/adfeed/store_db.py phase0/tests/test_google_push_schema.py
git commit -m "feat(store_db): Google push runs and dataSource column"
```

---

### Task 2: Mapper — canonical row → ProductInput

**Files:**
- Create: `phase0/adfeed/platforms/google/product_mapper.py`
- Test: `phase0/tests/test_google_product_mapper.py`

**Step 1: Failing test**

```python
def test_mapper_offer_id_is_sku_and_skips_fake_gtin():
    row = {"SKU": "NL-TEE-WHT-M", "优化后标题": "Tee", "颜色": "White", "价格": 18.0, ...}
    body = map_row_to_product_input(row, channel="online", content_language="en", feed_label="US")
    assert body["offerId"] == "NL-TEE-WHT-M"
    assert "gtin" not in body or not body.get("gtin")
    assert body["attributes"]["color"] == "White"
```

**Step 2: pytest — FAIL**

**Step 3: Implement mapper** from Chinese-key feed rows (same keys as `feed_generator.generate`). Empty color → omit color attribute (no Multicolor invent).

**Step 4: PASS + commit if requested**

---

### Task 3: Push client (mockable)

**Files:**
- Create: `phase0/adfeed/platforms/google/product_push.py`
- Test: `phase0/tests/test_google_product_push.py`

**Step 1: Failing test with FakeClient**

```python
class Fake:
    def __init__(self):
        self.calls = []
    def insert_product_input(self, *, merchant_id, data_source, product_input):
        self.calls.append(product_input["offerId"])
        if product_input["offerId"] == "BAD":
            raise PushItemError("INVALID", "no")
        return {"name": "accounts/1/productInputs/x"}

def test_push_records_ok_and_fail(tmp_path, ...):
    run = push_canonical_rows(store_id, merchant_id, data_source, rows, client=Fake())
    assert run["ok_count"] == 1 and run["fail_count"] == 1
```

**Step 2: FAIL**

**Step 3: Implement**
- `PushItemError`
- `LiveProductPushClient.insert_product_input` →  
  `POST https://merchantapi.googleapis.com/products/v1/accounts/{account}/productInputs:insert?dataSource=...`
- `push_canonical_rows`: map → bounded concurrency (ThreadPool or sequential first) → write push_items
- Honor field contract: skip rows that quality marked unpushable if flag present; never invent fields

**Step 4: PASS**

---

### Task 4: Feature flag + API route

**Files:**
- Modify: `phase0/adfeed/platforms/google/router.py`
- Modify: `phase0/adfeed/platforms/google/oauth.py` or small `config` helper for `GOOGLE_PUSH_ENABLED`
- Test: `phase0/tests/test_google_push_api.py`

**Step 1: Failing tests**
- `GOOGLE_PUSH_ENABLED` unset → `POST /api/app/google/push` returns 503
- With flag + mock body/`mock_result` → 200 and run id

**Step 2–4:** Implement `POST /api/app/google/push` (selected merchant + data_source required); `GET .../push/runs/{id}`; optional `mock_result` for CI like Meta issues sync.

**Do not** wire production deploy.

---

### Task 5: dataSource select helper

**Files:**
- Modify: `phase0/adfeed/platforms/google/merchant_client.py` (or new `datasources.py`)
- Modify: router — `GET/POST .../datasources`
- Test: `phase0/tests/test_google_datasources.py`

List/create API dataSources via Merchant API (mock in tests). Persist selected `data_source_name` on merchant row.

---

### Task 6: Sandbox UI CTA only

**Files:**
- Modify App Home / Google panel extension under `phase0/add-feed-ai/` (find existing Google issues UI)
- Keep Feed URL generation for other platforms; Google section: button label **推送到 Google（沙盒）**
- XML escape: secondary/advanced only if already have export UX — do not promote as primary

**Test:** manual or shallow component test if project has one; otherwise checklist in QA doc.

**Constraint:** no `shopify app deploy` to review app.

---

### Task 7: Wire push after quality rows (pipeline hook)

**Files:**
- Modify: `phase0/adfeed/pipeline.py` **or** call from router using same row-builder as `generate_feed_for_store` without writing XML
- Prefer: extract `build_feed_rows(store_id, ...)` if not already extractable — minimal refactor, no behavior change for XML path
- Test: `test_google_push_uses_same_offer_ids_as_xml` — mapper offerId equals XML `<g:id>` for one mock SKU

---

### Task 8: Docs + QA checklist update

**Files:**
- Update: `docs/plans/2026-08-30-google-mc-phase1-qa.md` (push + flag items)
- Spike note optional: `docs/plans/spikes/2026-08-31-merchant-product-inputs.md` with exact insert URL + dataSource requirement

---

### Task 9: Regression

Run:

```bash
cd phase0 && .venv/bin/pytest tests/test_google_*.py tests/test_feed_field_fixes.py tests/test_mock_catalog*.py -q
```

Expected: all pass. Confirm no production toml diffs in `git diff phase0/add-feed-ai/shopify.app.toml`.

---

## Execution handoff

Plan saved to `docs/plans/2026-08-31-google-api-push-dual-export.md`.

**1. Subagent-Driven (this session)** — one subagent per task, review between tasks  

**2. Parallel Session** — new session with executing-plans  

Which approach?
