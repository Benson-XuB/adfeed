# Reddit 冷启动主模式：1688 周更真实内容

**日期：** 2026-09-05  
**状态：** ACCEPTED — **信任/内容辅线**（主冷启动见 PLG Playbook）  
**原则：** 持续做真实 1688 内容 → 建立「懂中国供应链」人设 → 产品只顺带出现  

> **2026-09-06 更新：** 冷启动主引擎改为 **高意图获客 + Feed Checker**。  
> 见 [`2026-09-06-cold-start-plg-playbook.html`](./2026-09-06-cold-start-plg-playbook.html)（设计版） / [`2026-09-06-cold-start-plg-playbook.md`](./2026-09-06-cold-start-plg-playbook.md)。  
> 本文保留为测品与人设燃料，不再承担「唯一获客机」。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

相关：
- 痛点观察辅线：[`2026-09-05-reddit-cold-start-14-day-checklist.md`](./2026-09-05-reddit-cold-start-14-day-checklist.md)
- 产品信号池：[`2026-09-05-reddit-product-signals.md`](./2026-09-05-reddit-product-signals.md)

---

## 1. 模式（写死）

```
不是：淘东西 → 发帖 → 顺便打广告
而是：持续真实 1688 内容 → 人设 → 有人问再提工具
```

| 要 | 不要 |
|----|------|
| 真下单 / 真比价 / 真踩坑（至少一部分） | 纯截图二手、假装老司机 |
| 前 5～10 篇几乎不放产品链接 | 每篇文末硬塞 AdFeed / deltfu |
| 「我自己烦了才做了小工具」 | 「快来装我的 SaaS」 |
| 每周固定栏目 | 一天发多篇灌水 |
| 评论区有人问 How 再提工具 | 研究型 / founder research 硬帖（尤其 r/PPC） |

**转化漏斗（自然）：**

```
1688 找品 / 比供应商
  → 自己测
  → Reddit 发真实经验
  → 有人提问 / 认识你
  → 问到 Shopify·1688·Feed
  → 再自然提工具（AdFeed / waitlist）
```

**产品在叙事里的位置：** 只是 1688→Shopify→Google Shopping 链条里的一环，不是每篇主角。  
**Agent Marketplace：** 可当远期人设延伸，**不是**本阶段 KPI。

---

## 2. 时间盒（主辅分工）

| 节奏 | 做什么 | 优先级 |
|------|--------|--------|
| **每周 1 篇** | 固定栏目发文（见 §3） | **主** |
| **每天 20–30 分** | 回 2～3 条相关帖 + 记信号/痛点 | 辅 |
| 并行 | GMC 只读开发（独立分支）；定价不动 | 工程 |

不再要求「每天 5 条硬私信」作为主路径。

---

## 3. 周更栏目与主题轮换

**栏目名（建议）：** `What I found on 1688 this week`

| 周次类型 | 主题 | 为何有用 |
|----------|------|----------|
| A | I tested N products from 1688 under $X | 具体、可截图、易互动 |
| B | I tried N suppliers for the same product | 商业价值高（表格式） |
| C | Things I learned after buying from 1688 | 方法论、长尾搜索 |

**8 周示意（可循环）：** A → B → C → A → B → C → A → B  

坚持 **2～3 个月** 再评估：关注、私信、waitlist、自然问工具的次数。

### 发帖频道（优先）

1. r/dropshipping（主）  
2. r/ecommerce / r/shopify（经验贴，少 CTA）  
3. 相关时再考虑 r/AliExpress / 1688 向社区  

发前扫规则：禁硬广、禁纯推广；标题像经验不是广告。

---

## 4. 广告浓度（写死）

| 阶段 | 规则 |
|------|------|
| 第 1～5 篇 | **0 链接**；正文不提产品名 |
| 第 6～10 篇 | 最多一句「building tools around my own workflow」，仍可不放 URL |
| 评论有人问 How / tool | 再回：小工具 + `deltfu.com` 或 waitlist |
| 永远 | 不把「过审保证 / 假条码」当卖点撒谎；AdFeed 故事保持诚实 |

比例目标：**≥80% 内容 / ≤20% 产品暗示。**

---

## 5. 每篇必记（喂信号池）

发完或测品过程中，往 [`2026-09-05-reddit-product-signals.md`](./2026-09-05-reddit-product-signals.md) 或痛点表加：

- 踩到的供应链坑（MOQ、货不对图、物流）→ `ops-agent`  
- 进店后标题/品牌/GTIN/Shopping → `diag-gmc` / `fit-adfeed`  
- 「I manually…」→ `ops-manual`  

决议 A 不变：诊断叙事强化 **GMC**，不做独立 PPC Doctor。

---

## 6. 第 1 篇英文大纲（可直接扩写）

**建议标题：**  
`What I found on 1688 this week: 5 products under $10 (honest notes)`

**结构：**

1. **一句话开头** — 在测低价货源，记录价格/观感/是否会再买（不是荐股帖）。  
2. **方法** — 怎么搜的、是否看销量/复购、是否只要国内价（说明你人在链路哪一端）。  
3. **表格或逐条 5 个品**（每条尽量有）：  
   - 品类（不必全名品牌侵权）  
   - 1688 标价（¥）  
   - 粗算到手/物流备注  
   - 质量观感（图 vs 预期）  
   - 值不值得再买：Yes / Maybe / No  
4. **本周 1～2 条 lessons**（例：最便宜的不一定能卖；图好看货一般）。  
5. **结尾（第 1 篇：零广告）** — 欢迎问「你怎么筛供应商」；不放工具链接。

**第 1 篇禁止：** AdFeed、deltfu、early access、I built an app。

**配图：** 自己截的 1688 页（打码店铺敏感信息若需要）、或实物照；避免盗用别人测评图。

---

## 7. 类型 B 模板（供应商对比 — 高价值）

**标题例：**  
`I compared 3 1688 suppliers for the same [product type]`

| Supplier | Price | MOQ | Quality | Shipping note | Would buy again |
|----------|-------|-----|---------|---------------|-----------------|
| A | ¥… | … | ⭐… | … | Yes/No |
| B | … | … | … | … | … |
| C | … | … | … | … | … |

正文补：为什么选这三家、差在哪、若只能量产一家选谁。  
前几篇同样：**不硬广。**

---

## 8. 类型 C 模板（Things I learned）

子弹 5～7 条，每条：现象 → 我怎么判断 → 下次怎么做。  
可覆盖：最便宜≠最好、同品不同厂、MOQ、怎么初步判断靠谱、多供应商怎么管。  
软收尾（第 6 篇以后才考虑）：  
`I've been building some tools around the 1688 → Shopify workflow because I got tired of doing parts of this manually.`  
仍可不放链接，等评论问。

---

## 9. 成功怎么看（2～3 个月）

| 信号 | 健康 |
|------|------|
| 帖有讨论、有人追问细节 | ✓ |
| 有人私信/评：「你怎么弄到 Shopify / Feed」 | ✓ 再提工具 |
| waitlist / 安装有零星来自 Reddit | ✓ |
| 只有浏览没互动 | 换主题或加强真测证据 |
| 被标 spam / 删帖 | 减产品暗示、加强纯经验 |

---

## 10. 打卡小表（周更）

| 周 | 日期 | 类型 A/B/C | 标题 | 子版 | 0 链接？ | 评论问工具？ | 信号# | 笔记 |
|----|------|------------|------|------|----------|--------------|-------|------|
| 1 | | A | | | ☐ | | | |
| 2 | | B | | | ☐ | | | |
| 3 | | C | | | ☐ | | | |
| … | | | | | | | | |

---

## 修订

| 日期 | 变更 |
|------|------|
| 2026-09-05 | ACCEPTED：周更 1688 内容为主冷启动；回帖降为辅线；附第 1 篇大纲 |
