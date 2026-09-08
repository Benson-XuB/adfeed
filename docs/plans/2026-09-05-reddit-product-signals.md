# Reddit / 市场产品信号池（冷启动期）

**用途：** 14 天调研里「像产品、别急着做」的信号集中存放。  
**规则：** 只记录；满 20 条同类再讨论要不要立项。不做 Dev Research 发帖。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

相关：[`2026-09-05-reddit-cold-start-14-day-checklist.md`](./2026-09-05-reddit-cold-start-14-day-checklist.md)（痛点辅线）  
主冷启动：[`2026-09-05-reddit-1688-content-cold-start.md`](./2026-09-05-reddit-1688-content-cold-start.md)  

---

## 信号分类（怎么标）

| 标签 | 含义 |
|------|------|
| `diag-delivery` | 「广告/购物为什么不展示 / 不花钱」诊断类 |
| `diag-gmc` | Merchant Center limited / disapproved / 缺标识 |
| `ops-agent` | 中国代理 / 1688 / 履约 |
| `ops-manual` | 「I manually…」可软件化重复劳动 |
| `fit-adfeed` | 与现有 AdFeed 直接相关 |
| `fit-adjacent` | 模式相近，但是另一条产品线 |
| `fit-far` | 离当前公司远，只作观察 |

---

## 信号日志

| # | 日期 | 来源 | 原话/场景摘要 | 标签 | 适合做工具？ | 与 AdFeed | 状态 |
|---|------|------|---------------|------|--------------|-----------|------|
| 1 | 2026-09-05 | r/PPC · Bing 新户 Maximize Clicks 几乎无展示；Support 说「等一个月优化」；切 Manual/Enhanced CPC 后立刻有展示 | 新账户不知道为什么不花钱 → 不知查哪 → 被无效安抚 | `diag-delivery` `fit-adjacent` | **是（诊断路径）**；比「怎么优化广告」更适合工具 | **弱相关**：模式像「为什么不展示」，但渠道是 Microsoft Ads 出价，不是 Feed/GMC。AdFeed 更近的是 `diag-gmc` | 观察中 · 先攒同类 |

### 信号 #1 拆解（Ad delivery diagnosis）

```
新广告账户
  → 不花钱 / 几乎无展示
  → 不知道问题在出价、预算、审核、定向还是质量
  → Support：「等着优化」
  → 真实可操作：换出价策略 / 查验证 / 查份额丢失原因
```

**为什么比「怎么优化」更适合做工具**

| 「怎么优化广告」 | 「为什么不展示 / 不花钱」 |
|------------------|---------------------------|
| 开放、咨询型、难标准化 | 有限状态机：查清单 → 标红原因 |
| 强依赖人工判断 | 可做成：账户健康检查 / 诊断报告 |
| SaaS 难卖结论 | 可卖：一键诊断 + 下一步动作 |

**推荐 Reddit 搜索词（记频次，不发研究帖）**

- `not spending` / `no impressions` / `ads not showing`
- `low delivery` / `limited by` / `why aren't my ads showing`
- Shopping / GMC 侧：`Merchant Center limited` / `disapproved` / `missing GTIN`

---

## Brainstorm 纪要（2026-09-05）— 先对齐，不立项

### 看到了什么
另一份 AI 说得对：**「交付/展示诊断」是强工具形态**；优化建议是弱工具形态。

### 和你们现在的真实距离（重要）

| 路线 | 内容 | 评价 |
|------|------|------|
| **A. AdFeed 内（推荐接着做）** | GMC「为什么进不了 Shopping / limited / disapproved」只读诊断 | 已有 Spec + `feature/google-mc-issues`；和北星③一致；**就是 shopping 版 delivery diagnosis** |
| **B. 通用 PPC Delivery Doctor** | Google/Bing Ads 出价、预算、展示份额诊断 | 真需求，但是**新产品**；和 Feed 主线抢人；r/PPC 又禁 founder research |
| **C. 现在就开做 B** | — | **不建议**；冷启动 + 审核 + GMC 只读都还没收口 |

**结论：**  
把 Reddit 上学到的「诊断 > 优化」**迁移到 GMC 过审问题产品叙事**，不要立刻去做 Bing Maximize Clicks 检测器。

### 已决议（2026-09-05）

用户选择 **A**：  
「广告为什么不展示」→ **强化 AdFeed 的 GMC / Shopping 诊断叙事**（只读拒审/limited、指回改字段）。  
**不做**单独 PPC Delivery Doctor 产品线（除非将来 diag-delivery 单独爆量再议，默认否）。

落地含义：
- 冷启动话术 / App「过审问题」强调：**See why products aren’t showing — and what to fix**
- `feature/google-mc-issues` 继续作为下一程主功能
- Reddit 仍可观察 PPC 帖，但记入信号池时优先对照 `diag-gmc` / AdFeed 可借用点  

### AdFeed 可借用的产品话术（以后 UI/落地页）

- 不是：“Optimize your ads better”  
- 而是：“See why products aren’t showing in Shopping — and what to fix in your feed”

### 14 天里怎么收集（不写代码）

每遇到 `diag-delivery` 或 `diag-gmc`，在本表加一行，并在打卡表「当日笔记」写：`信号#N`。

满 **10 条 diag-gmc** → 加强 GMC 只读范围（含 limited，不只 disapproved）。  
满 **10 条 diag-delivery 且明确要 Ads 出价诊断** → 再单独讨论是否新开产品线（默认否）。

---

## 修订

| 日期 | 变更 |
|------|------|
| 2026-09-05 | 建池；录入信号 #1（Bing Maximize Clicks → Manual CPC）+ brainstorm |
