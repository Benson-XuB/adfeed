# Multi-platform modules (Google / Meta / TikTok) — 设计规格

**日期：** 2026-08-30  
**状态：** ACCEPTED（§1–§3 已确认）  
**产品形态：** AdFeed AI **应用内**多平台 Feed + 分平台连接闭环（不新建 Shopify App）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**相关：** Google 只读闭环 Spec `docs/plans/2026-08-30-google-mc-ads-read-loop-design.md`（迁入 `platforms/google`，不回退能力）

---

## 0. 决议摘要

| # | 决议 |
|---|------|
| 平台 | Google + Meta + TikTok |
| 深度 | **B**：连接账号 + 发布/挂 Feed +（后期）拒审/问题只读 |
| 代码结构 | **方案 A**：`adfeed/platforms/{google,meta,tiktok}/` 各成一模块，禁止糊在一起 |
| 交付 | 骨架一次立好；实现按 P0→P4 分期（见 §4） |

---

## 1. 问题与一句话方案

**问题：** 生成侧 UI 写死仅 Google；Meta/TikTok 生成器挤在 `multi_platform_feeds.py`；平台 API 若继续堆进 `api.py` 会无法维护。商家需要三家都能出 Feed，并分别连接平台账号做闭环。

**方案：** 统一「行数据」仍由 pipeline 生产；**每个广告平台一个包**，实现同一组能力接口；`api` / UI 只按平台挂载，不写 `if platform` 大泥球。

---

## 2. 模块边界（方案 A）

```
phase0/adfeed/platforms/
  common/          # Protocol + registry + 统一 Issue/Account DTO（无 HTTP）
  google/          # oauth, merchant/ads clients, feed export, sync, issues, router
  meta/            # oauth, catalog client, feed export, publish, sync, router
  tiktok/          # oauth, shop/catalog client, feed export, publish, sync, router
```

### 每平台能力面

| 能力 | 说明 |
|------|------|
| `export_feed` | 统一行 → 平台文件格式 |
| `oauth` | authorize / callback / token 存取 |
| `list_accounts` | Merchant / Catalog / Shop 列表与选择 |
| `publish_or_attach` | 挂 Feed URL 或 API 推品 |
| `sync_issues` | 拒审/商品问题 → 统一 Issue 形状（可后期实现） |
| `purge` | shop redact 清本平台表 |

**禁止：**

- `multi_platform_feeds.py` 同时承载 Meta+TikTok（拆入各自 `feed.py`）
- `api.py` 内联三家 HTTP
- 单一巨型 React 面板用 `if (platform)` 塞三家 OAuth
- 为过平台而编假 GTIN / 品牌 / **估算重量**（缺则标缺或引导填）

**字段主人：** 平台模块只映射与 API；不在 `title_guard` / `_enhance_title` 再按平台叠色码花色。

---

## 3. 数据与路由

### 表

| 模块 | 表 |
|------|-----|
| google | 保留现有 `google_oauth_tokens`、`google_merchant_accounts`、`gmc_product_issues`、`ads_metrics_daily` |
| meta | `meta_oauth_tokens`、`meta_catalogs`、`meta_product_issues`（后期） |
| tiktok | `tiktok_oauth_tokens`、`tiktok_shops`、`tiktok_product_issues`（后期） |

共用：`feed_files(platform,…)`、`product_assets(platform,…)`。

`purge_store_data` → 依次调用各平台 `purge(store_id)`。

### HTTP

```
/api/app/google/...
/api/app/meta/...
/api/app/tiktok/...
```

`api.py` 仅 `include_router`。

### Env

- Google：`GOOGLE_OAUTH_*`、`GOOGLE_ADS_*`
- Meta：`META_APP_ID`、`META_APP_SECRET`、`META_OAUTH_REDIRECT_URI`
- TikTok：`TIKTOK_CLIENT_KEY`、`TIKTOK_CLIENT_SECRET`、`TIKTOK_OAUTH_REDIRECT_URI`

---

## 4. UI

- Home「Ad platforms」：**Google / Meta / TikTok** 多选生成
- 分面板：`GmcIssuesPanel` / `AdsMetricsPanel`（google）、`MetaCatalogPanel`、`TikTokShopPanel`
- Workbench 按 `platform + country` 切换预览与 URL
- 配额：父商品 × 平台数 × 市场数（现有逻辑）

---

## 5. 分期交付

| 波次 | 内容 |
|------|------|
| **P0** | 目录骨架 + registry；迁 Google/Meta/TikTok **Feed 导出**入各包；UI 放开平台勾选；删/薄封装旧 `multi_platform_feeds` |
| **P1** | Google 连接/过审/Ads 迁入 `platforms/google`（行为不回退） |
| **P2** | Meta OAuth + 选 Catalog + publish/attach Feed |
| **P3** | TikTok OAuth + 选 Shop + publish/attach |
| **P4** | Meta/TikTok `sync_issues` 只读面板 |

审核中的生产：**不 deploy** 新 OAuth / 不改 listing 隐私至「连接 Meta/TikTok」就绪且审核允许。

---

## 6. 非目标

- Amazon / Pinterest 等其它平台（本 Spec 不预留实现，仅 registry 可扩展）
- 代投、改出价、自动改对方后台商品属性写假值
- 三家共用一个 OAuth 客户端文件

---

## 7. 验收（设计级）

- [ ] 三包目录清晰；`grep` 平台 HTTP 只落在本包
- [ ] 勾选 Meta/TikTok 能生成并得到独立 Feed URL
- [ ] Google 迁模块后既有测与手工过审路径仍可用
- [ ] TikTok/Meta 缺物流等字段时不静默编造
- [ ] redact 清掉对应平台 token/issues

---

## 8. 分支建议

- 实现：`feature/multi-platform-modules`（可从含 Google 闭环的分支或 `main` 拉，计划书里写清基线）
- 与 App Store 热修隔离：禁止混进审核生产 deploy
