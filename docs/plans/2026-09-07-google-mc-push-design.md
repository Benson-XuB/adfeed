# Google Merchant Center Push（API 直写）— 设计规格

**日期：** 2026-09-07  
**状态：** ACCEPTED（头脑风暴拍板）  
**产品形态：** AdFeed AI **嵌入式 App 内**能力（不新建第二个 Shopify App）  
**实现分支建议：** `feature/google-mc-push`（与 App Store 审核热修隔离）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 0. 用户是谁

| ✅ | ❌ |
|----|----|
| Shopify 商家，用 AdFeed 生成 Shopping 目录并投 Google | 「只下载 XML 的工具站用户」当主身份 |
| 目录常含 1688 导入脏数据，需要 review 再进 Google | 代运营代投、保证过审 |

---

## 1. 问题与一句话方案

**问题：** 当前主交付是「生成 XML / Feed URL，商家自己上传到 Merchant Center」——产品力弱，AdFeed 在「给文件」处停下。

**方案（选项 A · 推荐实现路线 1）：**  
Generate + 质量门 + review 工作台 **不变** → 主 CTA **Push to Google** → 用 Merchant API `productInputs.insert` 把未排除 SKU 写入该店绑定的 **AdFeed API Data Source** → 结果页成功 N / 失败 N；MC 目录能看到商品（**pending 即算 V1 成功**）。

XML / 持久 Feed URL **保留为次要「高级/备份」**，不再是主路径。

---

## 2. 与既有计划关系

| 文档 | 关系 |
|------|------|
| `2026-08-30-google-mc-ads-read-loop-design.md` | 原「先读拒审、不做自动写 GMC」。**本规格新增写侧 V1**；读拒审仍有价值，排在 Push 之后或共用 OAuth 后做 |
| `2026-09-04-next-gmc-rejection-read-loop.md` | 「下一程主线=读」在产品力上让位于 **Push**；读闭环改为 Push 之后的半环 |
| `2026-09-06-landing-feed-checker-gmc-tools.md` | 营销站只读工具 **不替代** App Push；OAuth 路径继续隔离 |

**北星：** Push 补齐「目录进 Google」；读拒审补齐「真实 Google 状态 → 改字段 → 再推」。先写后读。

---

## 3. 商家路径（§1 · ACCEPTED）

1. 照常 **Generate**（质量门 + review 工作台不变）  
2. 新主 CTA：**Push to Google**（XML/URL 降为高级/备份）  
3. 首次：Connect Google → 选 Merchant 账号 → 自动确保一个 **AdFeed API** data source  
4. Push：当前 Feed 中 **未排除** SKU 批量 `productInputs.insert`  
5. 结果页：成功 N / 失败 N（人话原因）+「在 Merchant Center 查看」  
6. **不等** Google approved；**不保证**过审  

### 「不等 approved / 不保证过审」含义

- **写入成功** = Merchant API 接受 `ProductInput`，商品进入 MC 目录（常为 pending）  
- **批准可投** = Google 审核结果，可能数小时～数天，AdFeed 不能承诺  
- V1 按钮成功停在「目录可见」；拒审读回与再推是后续版本  

---

## 4. 数据流（§2 · ACCEPTED）

**原则：** Push **不另起字段逻辑**。真相源 = 现有 Generate 商品行（与写入 `google-*.xml` 同一套主人字段）。Push 只换交付：映射 → API insert。

```
Shopify → Generate / 质量门 / workbench / 排除
       → 商品行列表
            ├─ 仍可 → XML + 持久 Feed URL（备份）
            └─ Push → ProductInput → productInputs.insert → 结果摘要
```

### ID 对齐

| Google | AdFeed |
|--------|--------|
| `offerId` | 现有 `g:id` / variant `sku`（`feed_generator.py`） |
| `itemGroupId` | `item_group_id` |
| `contentLanguage` | Feed 市场语言（如 `en`） |
| `feedLabel` | 市场标签（如 `US`） |
| `dataSource` | 该店绑定的 AdFeed **API** data source |

同 `offerId` + 同 data source 再 insert = **覆盖更新**。

### 字段

从现有行映射：`title`、`description`、`link`、`image_link`、`price`、`availability`、`condition`、`brand`、`color`、`size`、`size_system`/`size_type`、真 `gtin`（有才写）、`identifier_exists=no`（无码通道）、`pattern`（若有，不塞进 color）。

禁止在 Push 层编 GTIN、改 brand、出口叠标题（字段合同）。

### Data Source

- 每 store + merchant：确保一个 **type=API** 主数据源（名如 `AdFeed`）  
- 只写该源；**不**写入商家已有文件型（XML/URL）源  
- V1：**不**因排除而 API delete MC 商品  

### 执行

- 分批 insert、限速、单条失败不拖死整批  
- Token 失效 → 重新 Connect  
- 文案：已提交后 MC UI 可能延迟数分钟  

---

## 5. 明确不做（V1）与理由

| 不做 | 为什么 |
|------|--------|
| 写进商家已有 **文件型** data source | API 只能写 API 型源；混写会与手挂 Feed 互相覆盖、难排障 |
| Push 时编 GTIN / 改 brand / 出口叠标题 | 交付通道 ≠ 第二套洗数；脏数据在 Generate/review 修 |
| 等 approved 才报成功 | 审核时长不可控；会把「保证过审」绑进按钮 |
| 自动 delete 未推送 SKU | 排除 ≠ 删光；易误删他源商品；删除需显式动作（后置） |
| 代投 / 改出价 / AI 修图 / 第二个 App | 北星外 |
| 审核排队期改生产隐私 / listing Google 文案并 deploy | 防重审纠缠；开发走独立分支 + 本地 spike |

---

## 6. 存储与上线（§3 · ACCEPTED）

### 按店持久化

- Google OAuth tokens（服务端）  
- 选中的 `merchant_id`  
- AdFeed API `data_source_id`  
- 最近 Push 摘要（时间、成功/失败数、失败样例）  
- （可选）job id 防连点  

### OAuth

- Scope：`https://www.googleapis.com/auth/content`（Merchant 读写商品所需）  
- App 回调与营销站 `/api/public/google/oauth/*` **路径隔离**  
- 与日后「拒审只读」共用同一 App 连接  

### 排期

1. **审核中：** 设计 + 实现计划 + `feature/google-mc-push` 开发与测试店 spike；**不**动审核中生产 App 的 Google listing/隐私（除非明确接受重审）  
2. **过审后（或可动 listing 时）：** 合并主 CTA、生产 App redirect、灰度  
3. **营销站 Tools：** 可并行 landing-only，不替代 App Push  

### V1 验收

测试店：Generate → review → Push → MC 的 AdFeed API 源下出现对应 `offerId`（pending 可）→ 结果页计数正确。

---

## 7. API 锚点（实现锁定）

- `POST .../products/v1/accounts/{account}/productInputs:insert?dataSource=accounts/{account}/dataSources/{id}`  
- 需先有 API 型 primary data source（Data Sources API 创建或复用）  
- 参考：[productInputs.insert](https://developers.google.com/merchant/api/reference/rest/products_v1/accounts.productInputs/insert)、[Add and manage products](https://developers.google.com/merchant/api/guides/products/add-manage)  

Spike 须用真实测试账号验证：建源 → insert 1 条 → MC UI 可见。

---

## 8. 开放问题（实现期再钉，不挡设计）

1. 大批量（如 >500 SKU）是同步 HTTP 还是 `store_jobs` 后台任务 + 轮询进度  
2. 多市场 Feed（US/UK）是否一次 Push 一个 `feedLabel`，还是 UI 选市场  
3. Push 是否消耗现有 generate units / 另计费  

默认建议（可改）：V1 跟当前单一活跃 durable feed 的国家/语言；>100 条走 job；计费先跟 generate 同配额或不另扣（产品再定）。

---

## 9. 成功标准（产品一句话）

商家 review 完点 Push，**不用自己上传 XML**，就能在 Merchant Center 看到这批货。
