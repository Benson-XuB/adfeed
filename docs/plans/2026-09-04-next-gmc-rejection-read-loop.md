# 下一步优先：GMC 拒审读回闭环

**日期：** 2026-09-04  
**状态：** **SUPERSEDED IN PRIORITY（2026-09-07）** — 产品主交付改为 **Push to Google（API 写入）**；本文仍是 Push 之后的「读拒审」半环。  
**见：** [`2026-09-07-google-mc-push-design.md`](./2026-09-07-google-mc-push-design.md) · [`2026-09-07-google-mc-push.md`](./2026-09-07-google-mc-push.md)  
**原决定（仍有效作读侧规格）：** 审核稳定后 / Push 可用后，攻克 **Merchant Center 拒审原因读回 → App 内可见 → 引导改字段 → 再 Push/再生成**。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. 为什么是这一项

### 北星对齐

| 支柱 | 关系 |
|------|------|
| ① Feed 质量 | 已有生成侧质量门；本项**不改字段主人**，只把 Google 真实拒审指回已有字段 |
| ② 主图选择 | 拒审涉图 → 链到现有主图选择；**不做 AI 修图** |
| ③ 过审闭环 | **本项主交付** — 闭环缺的「读 MC 真实状态」半环 |

### 相对 1688→Shopify 市场痛点的位置

全网常见痛点里，与你们定位最贴、且**尚未交付**的是：

> 生成 Feed 并挂上 GMC 之后，商家仍要肉眼对照 Merchant Center，不知道哪个 SKU 因何被拒、该回 App 改哪一列。

已覆盖（不必用本项重做）：广告品牌确认、标题/色码清洗、无码通道、主图自选、生成前质量报告、持久 Feed URL。  
明确后置（本项仍不做）：AI 去水印、采集铺货、代发履约、代投出价。

---

## 2. 权威文档（已有，勿另起炉灶）

| 文档 | 作用 |
|------|------|
| [`2026-08-30-google-mc-ads-read-loop-design.md`](./2026-08-30-google-mc-ads-read-loop-design.md) | **Spec（ACCEPTED）** — 产品边界、分阶段、ID 对齐、UI、决议 1B/2A/3B/4B |
| [`2026-08-30-google-mc-ads-read-loop.md`](./2026-08-30-google-mc-ads-read-loop.md) | **Implementation Plan** — Phase 0 spike → Phase 1「过审问题」→ Phase 2 Ads 只读 |

本文件只锁定**排期优先级**；实现细节以以上两份为准。

---

## 3. 交付顺序（写死）

1. **Phase 0 — Spike（可立刻做）**  
   - 锁定 Merchant API / 只读 scope / offer_id 与 Feed `<g:id>` 对齐  
   - 本地沙盒 OAuth；**不**改审核中生产 App 的 OAuth / 隐私 / listing  
   - 分支：`feature/google-mc-issues`（与审核热修隔离）

2. **Phase 1 —「过审问题」（下一程主功能）**  
   - 连接 Google（MC 只读）→ 手动同步 → 问题列表 → 深链到现有改色/码/主图/品牌 → 再生成  
   - 验收：真实 MC 上至少 1 个 disapproved SKU 能在 App 出现对应原因

3. **Phase 2 — Ads 只读报表（Phase 1 有真实用户后再做）**  
   - 商品级花费/点击；增量授权；不代投

---

## 4. 硬门禁（动手前必守）

- **只读：** 不自动 PATCH GMC 商品、不改出价、不保证过审。  
- **字段合同：** 拒审提示改主人字段；禁止为对齐 Google 编假 GTIN / 假品牌 / 脏 color。  
- **审核隔离：** 审核排队期间不对生产 `shopify.app.toml` / 隐私页做 Google 相关 deploy；spike 与编码走独立分支。  
- **对不齐的 MC 问题进「未匹配」桶**，禁止猜绑到别的 SKU。

---

## 5. 成功标准（产品一句话）

商家能用 **真实 MC 拒审** 驱动「改什么 → 再生成」，无需离开 AdFeed 去猜。

---

## 6. 下一步动作

1. 从最新 `main` 拉 / 续作 `feature/google-mc-issues`  
2. 按 Implementation Plan **Task 0.1** 写 Merchant API spike 笔记  
3. Spike 通过后再开 Phase 1 DB + OAuth +「过审问题」UI  

---

## 修订记录

| 日期 | 变更 |
|------|------|
| 2026-09-04 | 锁定为下一程主线；链到 2026-08-30 Spec + Implementation Plan；补 1688 市场缺口语境 |
