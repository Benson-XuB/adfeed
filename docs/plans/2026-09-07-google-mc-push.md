# Google MC Push（API 直写）Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** App 内 Generate → review 后一键 `productInputs.insert` 把未排除 SKU 写入 Merchant Center（AdFeed API data source），MC 目录可见即成功。

**Architecture:** 复用 Generate 商品行；FastAPI 存 Google token / merchant_id / data_source_id；Merchant API 建 API 源 + 批量 insert；嵌入式 App 主 CTA「Push to Google」。审核期只在 `feature/google-mc-push` 开发，不改生产 listing/隐私。

**Tech Stack:** FastAPI、`store_db` SQLite、Google OAuth (`auth/content`)、Merchant API products/datasources v1、React Router App Home、现有 session JWT。

**Spec:** `docs/plans/2026-09-07-google-mc-push-design.md`（ACCEPTED）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**分支：** `feature/google-mc-push`（从最新 `main` 拉；勿与审核热修混提交）。

**可参考（勿整棵拷进审核路径）：** `phase0/adfeed/public_tools/google_oauth.py`、`google_issues.py`（营销站只读）；App 内 OAuth 用独立 redirect。

---

## Phase 0 — Spike（可立刻做）

### Task 0.1: Spike 笔记锁定 API

**Files:**
- Create: `docs/plans/spikes/2026-09-07-google-mc-push-spike.md`

**Step 1:** 文档写清并贴官方链接：

1. 创建 API primary data source 的 REST 路径与 body  
2. `productInputs.insert` URL、`dataSource` query、ProductInput 最小字段  
3. Scope：`https://www.googleapis.com/auth/content`  
4. `offerId` ↔ Feed `<g:id>` 假设  

**Step 2:** （可选）测试账号手动 OAuth + 插 1 条；记录 MC UI 是否可见。不把 secret 写入仓库。

**Step 3: Commit**

```bash
git add docs/plans/spikes/2026-09-07-google-mc-push-spike.md
git commit -m "docs(spike): lock Merchant productInputs insert for MC push"
```

---

### Task 0.2: 行 → ProductInput 纯函数 + 单测

**Files:**
- Create: `phase0/adfeed/google_mc_push/mapping.py`
- Create: `phase0/tests/test_google_mc_push_mapping.py`
- Create: `phase0/adfeed/google_mc_push/__init__.py`

**Step 1: 写失败测试**

```python
from adfeed.google_mc_push.mapping import feed_row_to_product_input

def test_maps_offer_id_and_does_not_invent_gtin():
    row = {
        "sku": "SKU-1",
        "title": "Black Dress Size M",
        "链接": "https://shop.example.com/products/d?variant=1",
        "image_link": "https://cdn.example/a.jpg",
        "price": "19.99 USD",
        "availability": "in_stock",
        "condition": "new",
        "brand": "Acme",
        "color": "Black",
        "size": "M",
        "item_group_id": "111",
        "identifier_exists": "no",
        "gtin": "",
    }
    body = feed_row_to_product_input(row, content_language="en", feed_label="US")
    assert body["offerId"] == "SKU-1"
    assert body["contentLanguage"] == "en"
    assert body["feedLabel"] == "US"
    attrs = body["productAttributes"]
    assert attrs["title"] == "Black Dress Size M"
    assert attrs["brand"] == "Acme"
    assert "gtins" not in attrs and not attrs.get("gtin")
    assert "invent" not in str(body).lower()
```

**Step 2:** `cd phase0 && .venv/bin/python -m pytest tests/test_google_mc_push_mapping.py -v` → FAIL  

**Step 3:** 实现 `feed_row_to_product_input`：只映射已有字段；空 GTIN 不写；`identifier_exists` 按行带出（API 字段名以 spike 为准）。从 `feed_generator` 实际 row key 对齐（中英列名以现网 generate 输出为准，必要时加适配）。

**Step 4:** 测试 PASS → Commit

```bash
git add phase0/adfeed/google_mc_push phase0/tests/test_google_mc_push_mapping.py
git commit -m "feat(mc-push): map feed rows to ProductInput without inventing GTIN"
```

---

## Phase 1 — 后端 OAuth + Data Source + Push API

### Task 1.1: store_db 表

**Files:**
- Modify: `phase0/adfeed/store_db.py`
- Create: `phase0/tests/test_google_mc_push_store.py`

**Step 1:** 测试 `upsert_google_connection` / `get_google_connection` 读写 `merchant_id`、`data_source_id`、encrypted/token fields。

**Step 2:** 表建议：

```sql
CREATE TABLE IF NOT EXISTS store_google_mc (
  store_id TEXT PRIMARY KEY,
  refresh_token TEXT,
  access_token TEXT,
  token_expiry TEXT,
  merchant_id TEXT,
  data_source_id TEXT,
  data_source_name TEXT,
  updated_at TEXT
);
CREATE TABLE IF NOT EXISTS store_google_mc_push_runs (
  id TEXT PRIMARY KEY,
  store_id TEXT NOT NULL,
  merchant_id TEXT,
  data_source_id TEXT,
  status TEXT,
  success_count INTEGER,
  failure_count INTEGER,
  failures_json TEXT,
  created_at TEXT
);
```

**Step 3:** 迁移与 helper → 测试 PASS → Commit

---

### Task 1.2: App 内 Google OAuth（与 public 隔离）

**Files:**
- Create: `phase0/adfeed/google_mc_push/oauth.py`
- Create: `phase0/adfeed/google_mc_push/router.py`
- Modify: `phase0/adfeed/api.py`（`include_router`）
- Modify: `phase0/.env.example`（`GOOGLE_APP_OAUTH_REDIRECT_URI` 注释）

**Step 1:** 路由前缀 `/api/app/google/`（需现有 Shopify app session）：

- `GET /oauth/start`  
- `GET /oauth/callback`  
- `GET /status`  
- `GET /accounts`  
- `POST /logout`  
- `POST /merchant` body `{ "merchant_id": "..." }`  

**Step 2:** Redirect 默认 `https://deltfu.com/api/app/google/oauth/callback`；本地用 env。**禁止**复用 `/api/public/google/oauth/callback`。

**Step 3:** 单测 mock token exchange → Commit  

---

### Task 1.3: Ensure API data source

**Files:**
- Create: `phase0/adfeed/google_mc_push/datasources.py`
- Create: `phase0/tests/test_google_mc_push_datasources.py`

**Step 1:** 测试：列表为空 → create 名为 `AdFeed` 的 API primary；已存在则返回其 id。

**Step 2:** 实现 HTTP 客户端（httpx）；错误映射人话（无 Admin 权限等）。

**Step 3:** PASS → Commit  

---

### Task 1.4: Push 端点

**Files:**
- Modify: `phase0/adfeed/google_mc_push/router.py`
- Create: `phase0/adfeed/google_mc_push/push.py`
- Create: `phase0/tests/test_google_mc_push_api.py`

**Step 1: 失败测试**

```python
def test_push_skips_excluded_and_reports_partial_failure(client, monkeypatch):
    # fixture: session store with 2 rows, 1 excluded
    # mock insert: first ok, second raises
    r = client.post("/api/app/google/push", headers=auth, json={"feed_file_id": "..."})
    assert r.status_code == 200
    body = r.json()
    assert body["success_count"] == 1
    assert body["failure_count"] == 1
    assert body["failures"][0]["offer_id"]
```

**Step 2:** 实现：

1. 校验已 Connect + merchant_id + data_source（否则 ensure）  
2. 加载当前 durable feed 商品行，过滤 `feed_excluded_skus`  
3. 逐条/小批 `insert`；写 `store_google_mc_push_runs`  
4. 返回成功/失败列表 + MC 深链（merchant 商品列表 URL）  

**Step 3:** V1 同步即可；若行数 >100，可先返回 400 建议缩小范围，或立刻接 `store_jobs`（见开放问题——默认 >100 用 job，本 Task 若时间紧可先硬限 100 并在 UI 说明）。

**Step 4:** PASS → Commit  

```bash
git commit -m "feat(mc-push): push feed rows via productInputs.insert"
```

---

## Phase 2 — App UI

### Task 2.1: Push 面板 + CTA

**Files:**
- Create: `phase0/add-feed-ai/web/app/components/GooglePushPanel.tsx`（或等价）
- Modify: `phase0/add-feed-ai/web/app/routes/app._index.tsx` 或 Feed 成功后区块（`FeedWorkbench` 旁）
- Modify: `phase0/add-feed-ai/web/app/lib/adfeed-api.ts`（API helpers）
- Modify: i18n 文案文件（en 主文案）

**Step 1:** UI 状态机：

- 未连接 → Connect Google  
- 已连接未选 MC → 账号选择  
- 就绪 → **Push to Google** 主按钮  
- Feed URL 复制降为次要链接/折叠「Advanced」  

**Step 2:** 结果区：成功/失败计数、失败样例、链接打开 MC。免责声明：「Does not guarantee Google approval。」

**Step 3:** 本地联调（mock API 或测试店）→ Commit  

```bash
git commit -m "feat(app): Push to Google CTA after generate review"
```

---

### Task 2.2: 防呆

**Files:** 同面板 + 后端

**Step 1:** 无 feed / 无可推 SKU → 禁用 Push + 说明  
**Step 2:** 短时防双击（前端 disabled + 后端 run 锁或 10s debounce）  
**Step 3:** Commit  

---

## Phase 3 — 文档与优先级指针

### Task 3.1: 更新下一程指针

**Files:**
- Modify: `docs/plans/2026-09-04-next-gmc-rejection-read-loop.md`（文首加：产品主交付优先 Push，见本设计；读闭环随后）  
- Modify: `docs/plans/2026-08-30-google-mc-ads-read-loop-design.md`（非目标「自动 PATCH」改为「V1 Push 见 2026-09-07 设计；拒审读回仍不做自动改字段」）

**Step 1:** 短段落交叉链接，避免两套「下一程」打架。  
**Step 2:** Commit docs only  

---

### Task 3.2: 过审后上线清单（不写代码）

**Files:**
- Create: `docs/plans/2026-09-07-google-mc-push-launch-checklist.md`

勾选：

- [ ] Cloud OAuth 增加 App redirect  
- [ ] 生产 env `GOOGLE_OAUTH_*` + App redirect  
- [ ] 隐私/listing 如需更新则提交审核  
- [ ] 测试店端到端 Push  
- [ ] 合并 `feature/google-mc-push`  

---

## 明确不做（实现时拒绝）

- 写文件型 data source  
- 编 GTIN / Push 层改 brand / 出口叠标题  
- 等 approved  
- V1 自动 delete  
- 审核期改生产 App Google 声明并 deploy  
- 把营销站 public OAuth 接到 App session  

---

## 执行顺序

0.1 → 0.2 → 1.1 → 1.2 → 1.3 → 1.4 → 2.1 → 2.2 → 3.1 → 3.2  

**Commit 策略：** 每 Task 结束一次；仅当用户要求时 commit（本计划步骤中的 commit 在执行会话按用户规则确认）。
