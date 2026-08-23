# Feed 预览 · 改源 · 快照回滚（设计）

**日期：** 2026-08-20  
**状态：** APPROVED（头脑风暴确认模型 A）  
**实现：** P0–P3 已落地（2026-08-20）— 预览 / 行编辑 / 快照 / 选图  
**后续 IA：** 工作台总表改为商品行 + 抽屉内按商品预览/编辑 Feed 条目 → 见 `docs/plans/2026-08-21-feed-workbench-product-rows-design.md`

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

**服从：** 北星（购物卡可读、可验收）+ 字段合同（改主人层，禁止出口叠补丁 / 整页 XML 手改当产品）。

---

## 1. 问题

1. 「更新 Feed」覆盖同一路径后，商家感觉旧版「没了」，且不知道新文件写到哪。  
2. 生成后只有链接，没有一览，无法判断标题/色/码是否像人会点的衣服。  
3. 需要能改，但行业标准不是「每个历史 XML 都可深度编辑」。

## 2. 选定模型（A）

与 Simprosys / DataFeedWatch / Channable / 官方 Google 通道一致的心智：

```text
改广告字段（源） → 预览当前结果 → 发布覆盖「当前」稳定 URL
                      ↑                    │
                      └── 快照只读可回滚 ───┘
```

| 做 | 不做（本设计） |
|----|----------------|
| 稳定 URL 一条给 GMC | 多版本 XML 工作区、动态多 URL 为主交付 |
| 表格一览 + 下载 XML/CSV | 整页 XML 编辑器 |
| 改 title/color/size（+ 可选图）写回主人层 | 在快照上改字段；出口再 `pin_*` |
| 发布前快照 N=5，可恢复为当前 | 任意历史版并行「都在投」 |

---

## 3. 数据流

```text
勾选商品 → 生成/更新
    → （若已有当前）先拷贝为快照
    → 写出「当前」XML/CSV（稳定路径与 URL）
    → 更新 feed_files
    → App「本轮结果一览」

商家改某行标题/色/码（或选 Feed 图）
    → 写回变体 / 广告资产主人层
    → 「应用到当前 Feed」= 同上生成管道（再打快照）

历史 → 预览/下载快照 或 「恢复为当前」
    → 恢复后若要改内容：仍走一览改源 → 再发布
```

**当前路径（不变）：**  
`feeds/{store_id}/{platform}/{lang}.xml`  
对外：`{PUBLIC_BASE_URL}/feeds/{store_id}/{platform}/{lang}.xml`

**快照路径：**  
`feeds/{store_id}/{platform}/_snapshots/{iso_timestamp}_{lang}.xml`  
（CSV 可选同名策略）

---

## 4. UI

### 4.1 结果一览（生成结束或「查看当前 Feed」）

- 表格一行 ≈ Feed 一条 item（变体）。  
- 首版列：缩略图 | 标题 | color | size | 价格 | 问题标记（quality fatal/warn 若有）。  
- 搜 SKU/标题、分页（禁止一次把整份 XML 塞进浏览器）。  
- 顶栏：复制当前 URL | 下载 XML | 下载 CSV。

### 4.2 编辑

| 操作 | 主人层 | 约束 |
|------|--------|------|
| 标题 | 广告资产 / 标题渲染输入 | 短可读；不叠出口补丁 |
| color / size | 变体清洗字段 | color 纯色；花色 → pattern，不进 color |
| Feed 图（P3） | feed_image 覆盖 | 沿用现有 image_patch 思路 |
| 品牌 | 店铺 `default_brand` 确认 | 不行内改成供应商默认名 |

保存后 **「应用到当前 Feed」** 走与「更新 Feed」同一生成管道。

### 4.3 历史快照

- 列表：时间、市场、条数。  
- 动作：预览 / 下载 / **恢复为当前**。  
- 不在快照上行编辑。

---

## 5. 存储与 API（概念）

### 5.1 存储

| 东西 | 位置 |
|------|------|
| 当前 Feed | 现有路径 + `feed_files` |
| 快照元数据 | 可选表 `feed_snapshots`（id, store_id, platform, country, file_path, item_count, created_at, job_id） |
| 一览行 | 从生成所用行 / 变体+资产 API 组装；不以「第二份商品库」当真相 |

### 5.2 API（可按期裁剪）

- `GET /api/app/feeds/{platform}/{country}/preview` — `limit`, `cursor`, `q`  
- 扩展现有 `quality/bulk_patch`、`image_patch`（或等价 PATCH）— 改主人字段  
- `POST /api/app/generate`（或 `…/apply`）— 发布：快照旧当前 → 写新当前  
- `GET /api/app/feeds/…/snapshots`  
- `POST /api/app/feeds/snapshots/{id}/restore`

**本地：** `ADFEED_PUBLIC_URL` 指向 API 隧道，复制链接才能打开当前文件（勿默认以为 deltfu.com 即本机刚生成的文件）。

---

## 6. 分期与验收

| 期 | 交付 | 验收 |
|----|------|------|
| **P0** | 一览 + 下载 + 复制稳定 URL | 生成后立刻看见标题/色/码；裤/裙/夹克各一可读 |
| **P1** | 行内改 title/color/size → 应用 | 一览与 XML 一致；color 不脏 |
| **P2** | 快照 N=5 + 恢复 | 覆盖前有旧份；恢复后当前 URL 内容变回快照 |
| **P3** | 一览内选 Feed 图 | 与 image_patch 打通 |

**回归：** 只看真商品购物标题是否更短更好懂；审查打分变好但标题变属性墙 → 回滚该改动思路。

---

## 7. 明确排除

- 安检大动画 / Magic Bar / 动态 URL 为主交付（北星未完成字段债前不开）。  
- 假 GTIN / 假 MPN / 静默 eprolo。  
- 把外部 AI / GMC 审查清单当需求整版改 Feed。  
- 恢复快照自动回写 Shopify 店内商品（只恢复广告 Feed 文件）。

---

## 8. 决策记录

| 问题 | 选择 |
|------|------|
| 最痛点 | D：看见 + 能改 |
| 竞品对齐后模型 | A：改源 + 预览 + 覆盖线上 + 快照 |
| 心智 / UI / API 三段 | 用户均回复 OK（2026-08-20） |
