# Multi-platform modules (Google / Meta / TikTok) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将 Google / Meta / TikTok 拆成独立 `platforms/*` 模块；先打通多平台 Feed 生成与 UI 勾选，再分期接各平台 OAuth 与发布/拒审闭环。

**Architecture:** `adfeed/platforms/{common,google,meta,tiktok}` + registry；`api.py` 只挂 router；UI 分面板。字段合同不变：平台层不编假值、不叠标题。

**Tech Stack:** FastAPI、现有 `pipeline` / `store_db`、httpx OAuth、React App Home。

**Spec:** `docs/plans/2026-08-30-multi-platform-modules-design.md`（ACCEPTED）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**分支：** `feature/multi-platform-modules`（建议从当前含 Google 闭环的分支或最新 `main` 拉齐后再开；**禁止**审核期生产 deploy Meta/TikTok OAuth）。

**Required skills during execution:** `@test-driven-development`；批次之间 `@executing-plans` checkpoint。

---

## Phase P0 — 骨架 + Feed 导出拆分 + UI 勾选

### Task 0.1: common Protocol + registry

**Files:**
- Create: `phase0/adfeed/platforms/__init__.py`
- Create: `phase0/adfeed/platforms/common/__init__.py`
- Create: `phase0/adfeed/platforms/common/types.py`
- Create: `phase0/adfeed/platforms/common/registry.py`
- Test: `phase0/tests/test_platforms_registry.py`

**Step 1: 写失败测试**

```python
def test_registry_lists_google_meta_tiktok():
    from adfeed.platforms.common.registry import list_platform_ids
    assert set(list_platform_ids()) >= {"google", "meta", "tiktok"}

def test_get_exporter_google():
    from adfeed.platforms.common.registry import get_platform
    p = get_platform("google")
    assert hasattr(p, "export_feed")
```

**Step 2:** `cd phase0 && .venv/bin/pytest tests/test_platforms_registry.py -v` → FAIL（模块不存在）

**Step 3: 最小实现**

- `types.py`: `PlatformId = Literal["google","meta","tiktok"]`；可选 Protocol `FeedExporter`（方法签名即可）
- `registry.py`: `_PLATFORMS` dict；`register` / `get_platform` / `list_platform_ids`
- 三包先放空 stub `platforms/{google,meta,tiktok}/__init__.py` 在 import 时 `register`

**Step 4:** 测通 → Commit `feat(platforms): registry skeleton for google/meta/tiktok`

---

### Task 0.2: 迁 Google feed export 入 `platforms/google/feed.py`

**Files:**
- Create: `phase0/adfeed/platforms/google/feed.py`（从 `feed_generator.generate_feed_xml` 薄封装或 re-export）
- Create: `phase0/adfeed/platforms/google/__init__.py`（register exporter）
- Modify: `phase0/adfeed/pipeline.py` 生成循环改为 `get_platform(plat).export_feed(...)`（或保留调用但路径指向新模块）
- Test: 现有 feed 测若有则跑；否则加 `tests/test_platforms_google_feed.py` 冒烟（空/一行不炸）

**Step 1–4:** TDD 保证 `export_feed` 写出与旧 Google XML 兼容的路径约定  
**Step 5:** Commit `refactor(platforms): move Google feed export behind platform module`

---

### Task 0.3: 拆 Meta / TikTok feed 出 `multi_platform_feeds.py`

**Files:**
- Create: `phase0/adfeed/platforms/meta/feed.py`（迁 `generate_meta_feed` / `save_meta_feed`）
- Create: `phase0/adfeed/platforms/tiktok/feed.py`（迁 TikTok CSV；**去掉或禁用静默 `_estimate_weight`**：缺重量则空字段或 skip+warning，禁止编造）
- Modify: `phase0/adfeed/multi_platform_feeds.py` → 薄 re-export 或删除并修一切 import
- Test: `phase0/tests/test_platforms_meta_feed.py`、`test_platforms_tiktok_feed.py`
- Test: `test_tiktok_feed_does_not_invent_weight` — 无重量行不得出现假 kg

**Step 5:** Commit `refactor(platforms): split Meta and TikTok feed exporters`

---

### Task 0.4: pipeline 只经 registry 导出

**Files:**
- Modify: `phase0/adfeed/pipeline.py`（`for plat in platforms` 段）
- Test: 扩展或加集成测：`platforms=["google","meta"]` 时两路径都 `save_feed_file`

**Commit:** `refactor(pipeline): export feeds via platforms registry`

---

### Task 0.5: UI 放开平台勾选

**Files:**
- Modify: `phase0/add-feed-ai/web/app/routes/app._index.tsx` — `PLATFORMS` 含 google/meta/tiktok
- Modify: `phase0/add-feed-ai/web/app/lib/i18n-messages.js`（若缺 label）
- 确认 Feed 列表/Workbench 已按 `feed.platform` 展示（已有则不动）

**Commit:** `feat(ui): enable Meta and TikTok platform checkboxes`

**P0 Done：** 商家勾选三平台可生成三份 Feed URL；无 OAuth。

---

## Phase P1 — Google 迁入 `platforms/google`（不回退）

### Task 1.1: 搬迁现有 `google_*.py` → `platforms/google/`

**Files:**
- Move/adapt: `google_oauth.py`、`google_merchant_client.py`、`google_ads_client.py`、`google_merchant_sync.py`、`google_ads_sync.py`、`google_offer_match.py`、`google_issue_actions.py`
- Create: `platforms/google/router.py`（从 `api.py` 剪出 `/api/app/google/*`）
- Modify: `api.py` → `include_router`
- 旧路径保留 **一行 re-export** 一版以免碎测，随后删
- Test: `pytest tests/test_google*.py` 全绿

**Commit:** `refactor(platforms): house Google OAuth/clients under platforms/google`

---

## Phase P2 — Meta 连接 + Catalog

### Task 2.0: Spike 文档（编码对接前）

**Files:** Create `docs/plans/spikes/2026-08-30-meta-catalog-api-spike.md`  
记录：OAuth scope、Catalog API、挂 product feed 方式、id 与 Feed `<id>` 对齐。

**Commit:** `docs(spike): Meta catalog OAuth and feed attach`

### Task 2.1: schema `meta_oauth_tokens` / `meta_catalogs`

**TDD** + `store_db` 或 `platforms/meta/store.py`  
**Commit:** `feat(meta): oauth and catalog tables`

### Task 2.2: `platforms/meta/oauth.py` + `router.py` start/callback/disconnect

**Commit:** `feat(meta): OAuth start/callback`

### Task 2.3: list/select catalogs + `publish_or_attach`（优先挂已生成 Feed URL）

**Commit:** `feat(meta): catalog select and feed attach`

### Task 2.4: UI `MetaCatalogPanel.tsx`

**Commit:** `feat(ui): Meta catalog connection panel`

---

## Phase P3 — TikTok 连接 + Shop

对称 P2：spike → schema → oauth → publish/attach → `TikTokShopPanel`  
**注意：** 不恢复估算重量；缺字段 UI 提示。

---

## Phase P4 — Meta/TikTok issues 只读

各包 `sync_issues` + 独立面板；Issue DTO 与 Google 对齐字段名便于 UI 复用**展示组件**，但 **client 仍分家**。

---

## 上线门禁

- [ ] App Store 审核结束或单独评估隐私/listing
- [ ] 各平台 env 仅服务器
- [ ] 隐私政策分写 Google / Meta / TikTok 只读或目录权限
- [ ] 字段合同自检：无静默假重量/假品牌

---

## Execution Handoff

Plan saved to `docs/plans/2026-08-30-multi-platform-modules.md`.

**执行方式：**

1. **Subagent-Driven（本会话）** — 每任务 subagent + 审查  
2. **executing-plans（本会话或另开）** — 按批次 checkpoint  

建议：先 **P0**（骨架+勾选生成），Google 迁模块（P1）可与 Meta spike（P2.0）并行文档；**P2/P3 OAuth 等审核后再部署生产**。

Which approach?
