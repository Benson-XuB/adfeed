# Google MC + Ads 只读闭环 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** AdFeed 应用内「过审问题」（MC 拒审只读）+ 后续「广告效果」商品级只读报表；一套 Google OAuth，先手后 Ads。

**Architecture:** FastAPI 存 Google tokens / issues / metrics；嵌入式 App Home 新区块。Phase 0 仅 spike+文档；Phase 1 MC 手动同步 + 多 Merchant；Phase 2 Ads 商品级 metrics。审核期禁止对生产 App 做 Google OAuth deploy。

**Tech Stack:** FastAPI、`store_db` SQLite、Google OAuth 2.0、Merchant API（spike 锁定）、Google Ads API（spike 锁定）、React Router App Home、现有 session JWT。

**Spec:** `docs/plans/2026-08-30-google-mc-ads-read-loop-design.md`（ACCEPTED；决议 1B/2A/3B/4B）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**分支约定：** 实现用 `feature/google-mc-issues`（从最新 `main` 拉）。**禁止**在审核热修 commit 里混入 Google 代码。

**Feed id 对齐提示：** 当前 XML `<g:id>` = variant SKU（见 `feed_generator.py`）；`item_group_id` 为产品组。Spike 必须用真实 MC 响应核对。

---

## Phase 0 — Spike（可先做，不改生产隐私/deploy）

### Task 0.1: 锁定 Merchant API 与 scope

**Files:**
- Create: `docs/plans/spikes/2026-08-30-google-merchant-api-spike.md`

**Step 1: 查阅官方文档并记录**

在 spike 文档写清：

1. 推荐 API 名称（Merchant API vs Content API for Shopping）与「读 product issues / status」的具体方法  
2. OAuth scope 精确字符串（只读）  
3. 响应里 offer id / item id 字段名样例  
4. 与 Feed `<g:id>`（SKU）对齐假设  

**Step 2: 本地用测试 Google Cloud 项目试一次 OAuth（可选）**

不把 client secret 写入仓库；只记「能列出 issues」或「阻塞原因」。

**Step 3: Commit**

```bash
git add docs/plans/spikes/2026-08-30-google-merchant-api-spike.md
git commit -m "docs(spike): lock Merchant API scopes and id fields for 过审问题"
```

---

### Task 0.2: 锁定 Ads 商品级 metrics 可行性

**Files:**
- Create: `docs/plans/spikes/2026-08-30-google-ads-product-metrics-spike.md`

**Step 1: 记录**

1. 商品级花费/点击用哪张 report view / resource（如 shopping_performance_view 等 — 以官方为准）  
2. 只读 scope 字符串  
3. 若某客户类型拿不到商品级：降级策略（账户+系列 + UI 标注）— 与 Spec §13 一致  

**Step 2: Commit**

```bash
git add docs/plans/spikes/2026-08-30-google-ads-product-metrics-spike.md
git commit -m "docs(spike): assess Ads product-level metrics for Phase 2"
```

**Gate:** Task 0.1 通过前不得开始 Phase 1 编码对接真实 Google。可用 mock 写测试。

---

## Phase 1 — 「过审问题」（Merchant）

### Task 1.1: DB schema — Google 连接与 issues

**Files:**
- Modify: `phase0/adfeed/store_db.py`（`init_db` / migrations 旁）
- Test: `phase0/tests/test_google_gmc_schema.py`

**Step 1: 写失败测试**

```python
def test_google_merchant_accounts_and_issues_tables_exist(tmp_path, monkeypatch):
    # point store_db to temp sqlite
    # init_db()
    # insert merchant account + issue row; fetch by store_id + merchant_id
    assert row["offer_id"] == "SKU-1"
    assert row["status"] == "disapproved"
```

**Step 2: 跑测确认失败**

```bash
cd phase0 && .venv/bin/pytest tests/test_google_gmc_schema.py -v
```

Expected: FAIL（表不存在）

**Step 3: 最小 schema**

表草案（实现时可微调列名，但语义不变）：

- `google_oauth_tokens(store_id, refresh_token_enc, scopes, updated_at)`  
- `google_merchant_accounts(store_id, merchant_id, display_name, is_selected, created_at)` — **多账号**  
- `gmc_product_issues(store_id, merchant_id, offer_id, product_id_internal NULL, status, reason_code, reason_text, raw_json, synced_at)`  
  - `product_id_internal`：对齐成功后填本店 product/variant 键；对不齐则 NULL（未匹配桶）

**Step 4: 测通 + Commit**

```bash
git add phase0/adfeed/store_db.py phase0/tests/test_google_gmc_schema.py
git commit -m "feat(store_db): schema for Google OAuth, merchants, GMC issues"
```

---

### Task 1.2: Offer id 对齐纯函数

**Files:**
- Create: `phase0/adfeed/google_offer_match.py`
- Test: `phase0/tests/test_google_offer_match.py`

**Step 1: 失败测试**

```python
from adfeed.google_offer_match import match_offer_to_sku

def test_exact_sku_match():
    assert match_offer_to_sku("RED-M", {"RED-M", "BLUE-S"}) == "RED-M"

def test_unmatched_returns_none():
    assert match_offer_to_sku("UNKNOWN", {"RED-M"}) is None

def test_no_fuzzy_steal():
    # must not bind UNKNOWN-RED to RED
    assert match_offer_to_sku("SKU-RED", {"RED"}) is None
```

**Step 2: 实现仅全等匹配（YAGNI：不做模糊）**

**Step 3: Commit**

```bash
git commit -m "feat(google): exact offer_id to feed SKU matching"
```

---

### Task 1.3: Merchant issues 同步服务（可 mock HTTP）

**Files:**
- Create: `phase0/adfeed/google_merchant_sync.py`
- Test: `phase0/tests/test_google_merchant_sync.py`

**Step 1: 测试用假 client**

```python
class FakeMerchantClient:
    def list_product_issues(self, merchant_id: str):
        return [
            {"offer_id": "SKU-1", "status": "disapproved", "reason_code": "image_missing", "reason_text": "..."},
            {"offer_id": "NOPE", "status": "disapproved", "reason_code": "other", "reason_text": "..."},
        ]

def test_sync_writes_matched_and_unmatched(store_fixture):
    # sync_merchant_issues(store_id, merchant_id, client=Fake..., sku_set={"SKU-1"})
    # assert one row product_id_internal set, one NULL
```

**Step 2: 实现 `sync_merchant_issues`** — 清旧 merchant_id 行或 upsert；禁止编造字段值。

**Step 3: Commit**

```bash
git commit -m "feat(google): sync GMC product issues with unmatched bucket"
```

---

### Task 1.4: OAuth 起止点（Phase 1 scopes only）

**Files:**
- Create: `phase0/adfeed/google_oauth.py`
- Modify: `phase0/adfeed/api.py`（新路由）
- Modify: `phase0/adfeed/config.py`（`GOOGLE_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI`）
- Test: `phase0/tests/test_google_oauth_routes.py`（mock token exchange）

**Routes 草案：**

- `GET /api/app/google/oauth/start` → redirect URL  
- `GET /api/app/google/oauth/callback` → 存 refresh token  
- `POST /api/app/google/disconnect`  
- `GET /api/app/google/merchants` / `POST .../merchants/select`  
- `POST /api/app/google/issues/sync`（**手动**）  
- `GET /api/app/google/issues?merchant_id=`  

**Step 1: 测 disconnect 清 token；sync 需登录 store**

**Step 2: 实现；secret 仅 env**

**Step 3: Commit**

```bash
git commit -m "feat(api): Google OAuth start/callback and manual GMC issues sync"
```

**注意：** 上线前才改隐私政策；审核中的生产 **不 deploy** 这些路由亦可先合进分支。

---

### Task 1.5: 原因 → 应用内行动映射（不写假值）

**Files:**
- Create: `phase0/adfeed/google_issue_actions.py`
- Test: `phase0/tests/test_google_issue_actions.py`

**Step 1:**

```python
def test_image_issue_maps_to_feed_image():
    assert suggest_action("image_missing")["action"] == "pick_feed_image"

def test_unknown_maps_to_read_only():
    assert suggest_action("weird_code")["action"] == "view_only"
```

映射表只链现有能力：`pick_feed_image` / `edit_color_size` / `confirm_brand` / `view_only`。  
**禁止**自动写 GTIN/brand/color。

**Step 2: Commit**

```bash
git commit -m "feat(google): map GMC issue codes to existing in-app actions"
```

---

### Task 1.6: App Home UI「过审问题」

**Files:**
- Create: `phase0/add-feed-ai/web/app/components/GmcIssuesPanel.tsx` (+ css module)  
- Modify: `phase0/add-feed-ai/web/app/routes/app._index.tsx`  
- Modify: `phase0/add-feed-ai/web/app/lib/adfeed-api.ts`  
- Modify: `phase0/add-feed-ai/web/app/lib/i18n-messages.js`（en + zh）

**UI 验收（与 Spec）：**

- 标题：**过审问题**  
- 未连接 → 连接 Google  
- 已连接 → **Merchant 下拉（多账号）** + 上次同步 + **同步**按钮  
- 列表：SKU / 状态 / 原因 / 去处理  
- 未匹配桶单独展示  

**Step 1: 接 API；无 Google 时不报错砸生成**  
**Step 2: Commit**

```bash
git commit -m "feat(ui): 过审问题 panel with multi-merchant manual sync"
```

---

### Task 1.7: shop/redact 与 disconnect 清 Google 数据

**Files:**
- Modify: `phase0/adfeed/store_db.py` `purge_store_data`  
- Modify: `phase0/tests/`（扩展现有 redact 测或新测）

**Step 1: 测 purge 删除 tokens/accounts/issues**  
**Step 2: Commit**

```bash
git commit -m "fix(privacy): purge Google tokens and GMC issues on shop redact"
```

---

### Task 1.8: Phase 1 手工验收清单

**Files:**
- Create: `docs/plans/2026-08-30-google-mc-phase1-qa.md`

列出：真实 MC 至少 1 条 disapproved → App 可见；去处理落到正确入口；断开后数据空。

```bash
git commit -m "docs: Phase 1 GMC 过审问题 QA checklist"
```

**Phase 1 Done 定义：** QA 清单全勾；字段合同自检：未为对齐编假值。

---

## Phase 2 — Ads 商品级效果（Phase 1 后）

### Task 2.1: Schema `ads_metrics_daily`

**Files:** `store_db.py` + `tests/test_google_ads_metrics_schema.py`

列草案：`store_id, ads_customer_id, date, offer_id NULL, campaign_id NULL, impressions, clicks, cost_micros, conversions, synced_at`  
`offer_id` 非空 = 商品级；空 = 账户/系列汇总行。

### Task 2.2: Ads sync（mock client）+ 增量 OAuth scope

**Files:** `google_ads_sync.py`, `google_oauth.py`（incremental Ads scopes）, API routes, tests

### Task 2.3: UI「广告效果」卡片

商品级表 + 链回「过审问题」；无商品级数据时降级文案。

### Task 2.4: Phase 2 QA doc

---

## 上线门禁（生产）

- [ ] App Store 审核已结束或单独评估改隐私/listing  
- [ ] `GOOGLE_OAUTH_*` 仅服务器 env  
- [ ] 隐私页更新 MC（+ Ads）只读说明  
- [ ] 不在审核中的 Partner 版本上强制用户授权 Google  

---

## 明确不做（实现时看到就停）

- 自动改 GMC / 代投 / 保证过审  
- 每日 cron（决议 2A）  
- 模糊 offer 匹配导致绑错 SKU  
- Meta/TikTok  
- 新 Shopify App  

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-08-30-google-mc-ads-read-loop.md`.

**Two execution options:**

1. **Subagent-Driven（本会话）** — 每任务新 subagent，任务间审查  
2. **Parallel Session（另开）** — 新会话用 executing-plans，按 checkpoint 推进  

**建议：** 审核排队期间只跑 **Phase 0 spike（Task 0.1–0.2）**；Phase 1 编码等上架稳定后再开。

Which approach?
