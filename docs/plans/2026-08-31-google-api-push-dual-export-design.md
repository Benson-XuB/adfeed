# Google API 推送 + XML 逃生舱 — 设计规格（方案 A3）

**日期：** 2026-08-31  
**状态：** ACCEPTED（§1–§3 已口头确认）  
**分支：** `feature/google-mc-issues`（或后续 `feature/google-api-push`）  
**隔离：** 仅本分支 / 本地沙盒；**禁止**影响 Shopify V1.0 审核中的生产 App、listing、隐私页、`shopify.app.toml`、线上 deploy

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**替代关系：** 部分取代 `docs/plans/2026-08-30-google-mc-ads-read-loop-design.md` 的 Phase 1（该文档从「只读」升级为本 Spec 的「写推送 + 读拒审」）。Ads Phase 2 仍以原 Spec 为准。

---

## 0. 一句话

内部仍走质量引擎与字段合同；Google **主路径**改为 Merchant API `productInputs` 推送；XML **保留为逃生舱**（代码可生成，沙盒 UI 不主推）；Meta / TikTok 仍 Feed/CSV。

---

## 1. 已决议

| # | 决议 |
|---|------|
| 方案 | **A** — 质量引擎不变，仅 Google 出口改 API |
| UI | **A3** — 双出口都做；沙盒 UI 只露「推送到 Google（沙盒）」；XML 留作不可控时的逃生 |
| 审核隔离 | 本分支不影响审核；生产默认仍可走现有 XML 路径直至上架后另开变更 |
| 写 API | **Merchant API** `productInputs.insert/patch/delete` + API 型 `dataSource`；**不用**已日落的 Content `custombatch` |
| Scope | `https://www.googleapis.com/auth/content`（复用现有 oauth） |
| 假值 | 仍禁止编 GTIN / 品牌 / 脏 color；缺字段 → 跳过或 FATAL，不静默补 |

---

## 2. 非目标（本阶段）

- 改审核中生产 OAuth / 隐私 / listing / deploy  
- 砍掉仓库内 Google XML 生成能力  
- Meta / TikTok 改为 API  
- Shopify 价库存 webhook 自动增量推（**P1.5**）  
- 代投、改出价、AI 修图  
- 保证 100% 过审  

---

## 3. 架构

```
Shopify → 质量引擎（字段合同）→ canonical rows
                ├─→ Google XML（保留；非沙盒主 UI）
                ├─→ Merchant API productInputs（「推送到 Google（沙盒）」）
                └─→ Meta XML / TikTok CSV（不变）
                         ↓
              reports.search / product issues →「过审问题」
                         ↓
              商家改字段 → 再推送（或 XML 逃生导出）
```

**开关：** `GOOGLE_PUSH_ENABLED=1` 才暴露推送 API/按钮；沙盒 `GOOGLE_OAUTH_*` 指向沙盒 GCP 项目。

---

## 4. OAuth 与 Merchant

| 项 | 决定 |
|----|------|
| 模块 | 复用 `phase0/adfeed/platforms/google/oauth.py` |
| Scope | `auth/content`；Ads 仍增量 |
| Merchant | 可多账号；需选当前 Merchant |
| dataSource | 必须为 Input=API 的 Primary 或 Supplemental；存 `data_source_name`（如 `accounts/{id}/dataSources/{ds}`） |
| Token | refresh_token 密封落库（已有） |

---

## 5. 推送管线

1. 复用 `generate_feed_for_store` **前半段**产出的规范化行（与 XML 同源）。  
2. `google_product_mapper`：行 → `ProductInput` JSON（`offerId` = 现有 `<g:id>` / SKU）。  
3. `push_products`：有界并发（建议 10–20）调用 `productInputs.insert`（或已存在则 `patch`）；429 指数退避。  
4. 每 SKU 记录成败 → `google_push_runs` / `google_push_items`。  
5. 支持「仅重试失败」；不因 API 报错自动改字段主人。

**增量（P1.5）：** webhook 价/库存 → 单品 `patch`。本 Spec 实现可不含。

---

## 6. 只读拒审（吸收原 Phase 1）

- 复用 `merchant_client.py`（`reports.search` / product issues）。  
- `offer_id` **全等**匹配本店 SKU；未匹配进单独桶。  
- UI：「过审问题」+ 深链到现有补色/码/主图/品牌路径。  
- 同步：MVP 仍可手动「同步」（与原决议一致）。  

---

## 7. UI（沙盒分支）

```
[ 连接 Google（沙盒）]
[ 选择 Merchant / API dataSource ]
[ 推送到 Google（沙盒）]   ← 主 CTA
[ 过审问题 | 同步 ]
高级 / 逃生：导出 Google XML（弱化或不进主屏）
```

文案带「沙盒」；不上架 listing。生产切换时另开变更去掉「沙盒」字样。

---

## 8. 库表

| 对象 | 用途 |
|------|------|
| `google_merchant_accounts.data_source_name`（或旁表） | 选中的 API dataSource |
| `google_push_runs` | store_id, merchant_id, status, ok_count, fail_count, started_at, finished_at |
| `google_push_items` | run_id, offer_id, status, error_code, error_text, raw_json |
| 已有 `google_oauth_tokens` / `gmc_product_issues` | 复用 |

---

## 9. 与北星关系

见 `2026-08-12-mvp-north-star.md` **2026-08-31 修订**：Google 交付物从「仅 Feed URL」扩展为「API 目录推送为主、XML 逃生」；支柱①②与字段合同不变；③闭环改为「修正 → 再推送」。

---

## 10. 验收清单（本分支沙盒）

- [ ] 沙盒 OAuth → Merchant + API dataSource  
- [ ] 「推送到 Google（沙盒）」对 mock 目录 ≥20 SKU 可跑通，成败可查  
- [ ] 同 offer_id 拒审出现在「过审问题」→ 改字段 → 再推送  
- [ ] `GOOGLE_PUSH_ENABLED` 未开时推送不可用  
- [ ] XML 生成回归仍绿；主 UI 不主推 Feed URL  
- [ ] 无生产 toml / 隐私 / listing 改动  

---

## 11. 风险

| 风险 | 对策 |
|------|------|
| Content API 日落 / 无 custombatch | 直接上 Merchant `productInputs` + 并发 |
| dataSource 配错抢 ownership | 首次引导创建/选择 API source；文档写明 |
| 审核纠缠 | 分支隔离；生产不配 push env |
| 大批量 429 | 有界并发 + 退避 + 分 run 重试 |
| 脏目录硬塞 | 质量门 FATAL 不推；禁止假值 |

---

## 12. 下一步

1. Implementation Plan：`docs/plans/2026-08-31-google-api-push-dual-export.md`  
2. 本地实现 + mock client 测试  
3. 真实沙盒 OAuth（负责人在 GCP Console 配项目 / 测试用户）  
4. 上架稳定后再议生产默认切 API  

---

## 修订记录

| 日期 | 变更 |
|------|------|
| 2026-08-31 | ACCEPTED：A + A3；§1–§3 确认后落盘 |
