# Google MC + Ads 只读闭环 — 设计规格（SDD · Spec）

**日期：** 2026-08-30  
**状态：** ACCEPTED（开放问题已答，2026-08-30）— 可写 Implementation Plan；审核期仍禁止动生产 Google OAuth  

**分支：** `docs/google-mc-ads-read-loop`（与 App Store 审核中的生产改动隔离）  
**产品形态：** AdFeed AI **应用内扩展模块**（不新建 Shopify App / 不换 Client ID）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 0. 用户是谁（写死，避免再漂）

| ✅ | ❌ |
|----|----|
| **Shopify 商家**（在 Admin 装 AdFeed、维护目录、投 Google） | 「1688 卖家」 |
| 目录中**常有从 1688 导入的商品**（脏标题/供应商名进 brand 等） | 在 1688 开店卖货的人 |

对外定位仍可提 1688 作为**货源场景**；身份永远是 Shopify merchant。

---

## 1. 问题与一句话方案

**问题：** Feed 生成后，商家在 Merchant Center / Ads 侧的「被拒原因」和「花得值不值」与 App 断开，只能肉眼对照。

**方案（选项 C，分阶段）：**  
同一套 Google 连接 + **先读后写**：

1. **Phase 1（A）：** Merchant Center 商品审核状态 / 拒审原因 → 映射到本店 SKU → 引导改字段 / 再生成  
2. **Phase 2（B）：** Google Ads 花费 / 点击 / 系列表现（只读报表）→ 链回 Phase 1 问题列表  

**不做：** 代投、改出价、自动改 GMC 商品、保证过审、AI 修图、新开第二个 App。

---

## 2. 与北星关系

| 北星支柱 | 本规格 |
|----------|--------|
| ① Feed 质量 | 不改字段主人；拒审只**提示**改哪些已有主人字段 |
| ② 主图选择 | 拒审若涉图 → 链到现有主图选择，不新做修图 |
| ③ 过审闭环 | **本规格主交付** = 闭环的「读真实 Google 状态」半环 |

字段合同门禁：缺数据仍由 UI 让商家填或从变体算；**禁止**为对齐 Google 而编假 GTIN / 假品牌 / 脏 color。

---

## 3. 非目标（Explicit non-goals）

- 审核排队期间改生产 OAuth / 隐私文案导致**再触发审核纠缠**（Phase 0 仅文档与本地 spike）  
- Google Ads 建系列、PMax、出价、素材  
- 自动 PATCH Merchant Center 商品  
- Meta / TikTok  
- 独立「过审」App Store 产品  

---

## 4. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│ AdFeed AI (Shopify embedded)                            │
│  App Home: Generate | Feed URL | [NEW] Google insights  │
└───────────────┬──────────────────────────▲──────────────┘
                │                          │
                ▼                          │
┌───────────────────────────┐   ┌──────────┴──────────────┐
│ FastAPI (deltfu.com)      │   │ store_db                │
│ google_oauth              │──▶│ google_tokens           │
│ merchant_issues_sync      │──▶│ gmc_product_issues      │
│ ads_metrics_sync (P2)     │──▶│ ads_metrics_daily       │
└───────────┬───────────────┘   └─────────────────────────┘
            │
            ▼
┌───────────────────────────┐
│ Google Cloud project      │
│ OAuth (incremental)       │
│ 1) Merchant API (issues)  │
│ 2) Ads API (metrics)      │
└───────────────────────────┘
```

**原则：** 一套 Google OAuth；Ads scope **增量授权**，不强迫 Phase 1 用户开 Ads。

---

## 5. 分阶段交付

### Phase 0 — 现在（审核期）· 本分支只做这个

| 交付 | 说明 |
|------|------|
| 本 Spec（本文） | 产品/技术边界锁定 |
| （可选）Implementation Plan | 确认 Spec 后再写，仍不碰生产密钥与线上 deploy |
| Spike 笔记 | 真实 API 名称、scope 字符串、offer_id 对齐实验 — 可另开 `*-spike.md`，**不写进生产** |

**禁止：** 改 `shopify.app.toml` 生产 scopes、改隐私页、对审核中 App 做 Google 相关 deploy。

### Phase 1 — Merchant Issues（上架稳定后优先）

**用户故事：**  
作为 Shopify 商家，我连接 Merchant Center 后，能在 AdFeed 看到哪些已生成 Feed 的 SKU 被拒/受限及原因，并跳去改色码/主图/品牌后重新生成。

**功能清单：**

1. 「连接 Google」→ 授权 **MC 只读** → 选择 Merchant 账号  
2. 「同步商品问题」→ 拉取 item issues / product status  
3. 与本店 `product` / feed row 按 **offer_id / item_id** 对齐（对齐规则见 §7）  
4. UI：问题列表（状态、原因码、人类可读摘要、深链到现有编辑）  
5. 空状态：未挂 Feed / 未连 Google / MC 无匹配商品  

**验收：**

- [ ] 至少 1 个真实 MC 账号：disapproved SKU 能在 App 出现对应原因  
- [ ] 点击问题能落到现有「缺色/缺码/主图/品牌」路径之一（无则只展示文案，不编假值）  
- [ ] 断开连接后 token 删除，列表清空  

### Phase 2 — Ads 只读报表（Phase 1 有真实用户后再做）

**用户故事：**  
作为已连接 Ads 的商家，我能看到近 7/30 日花费、点击、展示（及可得的转化），并一键回到 Phase 1 的拒审列表。

**功能清单：**

1. 增量授权 Ads 只读 → 选择客户账号（CID）  
2. 同步 campaign / 账户级 metrics（先账户+系列，商品级后置）  
3. App 内简报卡 +「查看 Feed 问题」入口  

**验收：**

- [ ] 花费/点击数字与 Ads UI 同时间窗大致一致（允许 API 延迟）  
- [ ] 无 Ads 的用户可跳过，不影响 Phase 1  

---

## 6. OAuth 与 Scope（草案 · Spike 时核对官方最新名）

| 阶段 | 能力 | Scope 方向（草案） |
|------|------|-------------------|
| P1 | 读 Merchant 商品/问题 | Merchant API 只读相关 scope（spike 锁定精确字符串） |
| P2 | 读 Ads 报表 | Ads API 只读（如 `adwords` 只读类；spike 锁定） |

**UX：**

1. 首次只请求 **P1 scopes**  
2. 点「连接广告数据」再请求 **P2 scopes**（incremental）  

**存储：** `shop_domain` → encrypted refresh_token、google_account、merchant_id、optional ads_customer_id、updated_at。  
密钥仅服务器 env，不进仓库。

---

## 7. ID 对齐（Phase 1 成败关键）

Feed 侧已有稳定 id（Shopify variant / 自有 offer id — 以当前 `feed_generator` 输出为准）。

**规则（实现前 spike 必须验证）：**

1. 同步时以 Feed XML/CSV 中的 `id` / `item_group_id` 为主键候选  
2. 与 MC API 返回的 offer id **字符串全等**优先；次选规范化（去前缀 `shopify_` 等，若我们确有此前缀）  
3. 对不齐的 MC 问题：**单独「未匹配」桶**，禁止猜错绑到别的 SKU（防字段合同事故）  

**禁止：** 为对齐而改写 title/color/brand/GTIN 假值。

---

## 8. UI 草图（App Home 扩展，非新 App）

```
[ 生成 Feed ]  [ Feed 链接 ]
[ 过审问题 ]  ← Phase 1
  未连接 → [连接 Google]
  已连接 → Merchant 选择器（可多账号）| 上次同步 [同步]
  列表：SKU | 状态 | 原因 | [去处理]
[ 广告效果 7日 ]     ← Phase 2（商品级 metrics；可灰显「连接广告账号」）
  花费 | 点击 | 展示（按商品/offer）
  [查看过审问题]
```

文案避免保证过审；避免 Features/listing 未批准前就写「连接 Google」（上架后再改 listing）。

---

## 9. 隐私 / 合规 / 审核

| 项 | 要求 |
|----|------|
| 隐私政策 | 上线 P1 前增加：连接 Google、读 MC 商品问题；P2 增加 Ads 效果只读 |
| Shopify listing | P1 上线后再更新描述；**审核中的版本不要为 Google 改 listing** |
| 数据删除 | `shop/redact` / 断开连接时删除 Google tokens 与缓存 issues/metrics |
| 客户数据 | 仍不读 Shopify customers；Google 侧也不拉买家 PII |

---

## 10. 商业化（可后置，规划占位）

| 能力 | 建议包装 |
|------|----------|
| 现有生成 | 现配额 |
| P1 同步 | Starter+ 含定期同步，或消耗诊断次数 |
| P2 报表 | Growth 含 Ads 简报 |

先功能后拆价；本 Spec **不**要求改 Billing 表结构。

---

## 11. 风险与对策

| 风险 | 对策 |
|------|------|
| Ads API 准入慢 | 交付顺序强制 P1→P2 |
| 商家无 MC | 空状态 + 引导「先把 Feed URL 挂上」 |
| offer_id 对不齐 | 未匹配桶；spike 不过不进 P1 开发 |
| 审核期改生产 | 本分支只文档；hotifix 走 `main` / 审核用分支 |
| Scope 吓跑用户 | 分步授权 |

---

## 12. 成功标准（产品）

**P1：** 商家能用真实 MC 拒审驱动「改什么 → 再生成」，无需离开 AdFeed 去猜。  
**P2：** 商家能在 AdFeed 看到花费/点击，并回到 P1 问题，而不是做成广告投放台。

---

## 13. 开放问题 — 已决议

| # | 决议 | 含义 |
|---|------|------|
| 1 | **B.「过审问题」** | P1 模块标题用「过审问题」，不用「Google 商品状态」 |
| 2 | **A. 仅手动同步** | MVP 不设每日 cron；用户点「同步」才拉 MC |
| 3 | **B. 支持多个 Merchant** | MVP 可绑多个 MC 账号（需账号切换 UI + 按 merchant_id 存 issues） |
| 4 | **B. 要商品级 metrics** | P2 第一版做到商品级效果（不只账户+系列）；实现成本更高，spike 必须验证 Shopping/商品维度可用性 |

### 决议对设计的影响（补丁）

- **§5 P1 UI：** 入口文案改为「过审问题」。  
- **§5 P1 同步：** 仅手动；`上次同步时间` +「同步」按钮。  
- **§6 / 存储：** `merchant_id` 一对多（每 shop 多行或 JSON 列表）；UI 需「当前 Merchant」选择器。  
- **§5 P2：** metrics 表需支持 product/offer 维度（或 shopping performance view）；若 Google API 对某账户拿不到商品级，降级展示账户+系列并标注「本账号无商品级数据」。  

---

## 14. 下一步

1. ~~开放问题~~ → 已答（1B/2A/3B/4B）  
2. ~~Implementation Plan~~ → `docs/plans/2026-08-30-google-mc-ads-read-loop.md`  
3. **另开** `feature/google-mc-issues`；审核期优先只做 Phase 0 spike  
4. Phase 1 编码等上架稳定后再合入生产 deploy  

---

## 修订记录

| 日期 | 变更 |
|------|------|
| 2026-08-30 | 初稿 DRAFT；分支 `docs/google-mc-ads-read-loop` |
| 2026-08-30 | 开放问题决议 1B/2A/3B/4B；状态 ACCEPTED |
| 2026-08-30 | 链到 Implementation Plan |
