# AdFeed — 设计文档盘点（纠偏）

**日期：** 2026-08-14  
**状态：** **LOCKED 索引** — 以后改 Feed / 写计划，先看本文再看子文档  
**为何写：** 计划文件叠了 20+ 份；愿景稿、实现稿、已废弃范围混在一起。跟着「审查清单」和「急迫 UX」打补丁，购物标题越改越差。本文把 **合理 / 不合理 / 已过期** 一次说清。

---

## 0. 权威顺序（冲突时只认这个）

```
1. docs/plans/2026-08-12-mvp-north-star.md          ← 做什么（MVP）
2. docs/plans/2026-08-14-feed-field-contract.md     ← 怎么改 Feed 字段（禁止出口补丁）
3. 本文（设计盘点）                                ← 哪份子文档还能当需求
4. 各 LOCKED / ACTIVE 子设计
5. 需求总册、愿景稿                                 ← 只作 backlog，不当冲刺需求
```

**口头「另一边 AI 审查清单」永远不进入权威顺序。** 它是输入，不是规格。

---

## 1. 一句话结论：偏在哪

| 偏航 | 表现 | 根因 |
|------|------|------|
| **字段没有主人** | color 塞 Style、title 叠 Size/花色/材质 | 出口补丁满足 uniqueness / 审查打点 |
| **文档没有主人** | 北星说后置动画/去水印，旧 UX 稿仍写「急做」 | 愿景稿未标 SUPERSEDED |
| **验收错了** | 重复标题少了、假 MPN 没了，购物卡却更丑 | 用审查分数代替「像不像衣服」 |
| **缺数据两种极端** | 要么不管，要么编 eprolo / 假 MPN | 没有「引擎算 + UI 确认」合同 |

**合理方向没变：** 1688→Shopify→可过审 Shopping Feed；可解释；不造 GTIN；价币种真；主图自选。  
**不合理的是做法：** 用多层出口润色和外部打分表当产品。

---

## 2. 文档分类

### A. 必须遵守（LOCKED）

| 文档 | 判词 | 说明 |
|------|------|------|
| `2026-08-12-mvp-north-star.md` | **合理** | 三大支柱对；后置清单对；继续 LOCKED |
| `2026-08-14-feed-field-contract.md` | **合理** | 纠偏合同；改 title/color/size 必看 |
| 本文 | **合理** | 子文档能否当需求的索引 |

### B. 仍有效，但要按合同读（ACTIVE）

| 文档 | 判词 | 怎么读 |
|------|------|--------|
| `2026-08-10-high-quality-feed-engine-design.md` | **大体合理，局部过期** | S1 无码/One Size/Multicolor/价币种/敏感 **留**。流水线里 S7「去水印/白底」**已废**，以 image-picker 为准。标题「重构」不得再解释成出口叠层。 |
| `2026-08-09-price-currency-markets-design.md` | **合理** | 禁静默换汇；落地页币种一致 |
| `2026-08-09-feed-quality-gate-design.md` | **合理** | AUTOFIX/WARN/FATAL；FATAL 仍进 Feed |
| `2026-08-12-feed-image-picker-mvp.md` | **合理** | 主图自选；不做 AI 修图 |
| `2026-08-12-store-website-compliance-lite.md` | **合理** | 投广告前网站诊断；不挡生成 |
| `2026-08-11-sensitive-compliance-p0/p1.md` | **合理** | 护号；软化 + adult |
| `2026-08-12-availability-markets-presentment.md` | **合理** | 库存真值；availability 二元 |
| `2026-08-11-feed-link-allowlist-deferred.md` | **合理（明确后置）** | Query 白名单 DEFER |
| `2026-08-11-bulk-fallback-confirm-ux.md` | **部分合理** | Multicolor/One Size 可改 **留**；完整 Magic Bar 抽屉按北星后置 |

### C. 易误导 — 标 SUPERSEDED / 只作历史

| 文档 | 判词 | 问题 |
|------|------|------|
| `2026-08-10-gmc-approval-loop-ux-design.md` | **愿景可留，范围已废** | 仍写动态 URL 为主、去水印、安检大动画为「急」。北星已后置。**不要按本文排期。** |
| `2026-08-10-adfeed-requirements-inventory.md` | **需求池，不是冲刺单** | A–G 全家桶（短视频/B2B/认证厂）会把人拉偏。只当 backlog；实现以北星为准。 |
| `2026-08-11-title-keep-variant-attrs-design-diff.md` | **半过期** | 「标题脑与属性脑分离」**合理**。但写了 `title_guard.polish` 后置对齐、Brand 前缀 eprolo 保持 —— **与字段合同冲突**。属性合同留；标题出口叠层废。 |
| `2026-08-11-variant-attrs-scene-priority.md` | **实现计划，部分已做** | 场景有则加、variant_attributes **合理**。不要再据此加 title_guard 层。 |
| `2026-08-12-material-desc-en-hardening.md` | **部分合理** | 材质英文化、重 CJK 描述处理 **可留**。禁止把整页尺码表 + 属性墙当最终 description。 |

### D. 基础设施 / 历史（不挡 Feed 质量）

| 文档 | 判词 |
|------|------|
| `2026-08-06-shopify-app-multi-platform*.md` | App 骨架历史；技术栈以北星锁定为准 |
| `2026-08-06-e2e-checklist.md` | 检查表，可留 |
| `2026-08-09-price-currency-markets.md` / `2026-08-10-high-quality-feed-engine.md` | 实现计划；以对应 design + 字段合同为准，过时步骤勿机械执行 |

---

## 3. 产品决策：哪些合理，哪些不合理

### 3.1 继续成立（不要动摇）

1. **购物 Feed 过审闭环** 是胜负手，不是技术栈炫技。  
2. **不造 GTIN**；无码 = `identifier_exists=no` + **店品牌**（UI 确认）。  
3. **尺码空 → One Size**（服饰）；**色空 → 抽取再 Multicolor**。  
4. **价币种与落地页一致**，禁静默 FX。  
5. **主图用户自选**，不做默认 AI 去水印。  
6. **FATAL 仍进 Feed**，界面红灯，不叫绿通。  
7. **能自动的自动；不能编的 UI 带着填** —— 不是「店没有就不管」，也不是「店没有就编」。

### 3.2 曾经合理、实现跑歪了（要纠）

| 决策 | 原意 | 歪法 |
|------|------|------|
| 标题 AI 重构 | 短、可搜、品类在前 | 出口再插花色/Size/材质/Plus，变属性墙 |
| 变体唯一 | 同组 color+size(+pattern) 不撞 | 把 Style/花色塞进 color |
| brand 兜底 | 店品牌 > 默认 | 静默全站 `eprolo` |
| 无码 + brand | 1688 无条码可过机 | 假 MPN（已删）；外部审查要求删 brand（**不要听**） |
| title_guard | 品类纪律（禁乱写 tummy） | 变成第二标题引擎 |

### 3.3 不合理 / 明确不做（写进合同的）

| 项 | 为何不合理 |
|----|------------|
| 出口 `pin_*` / enhance 后再插词 | 补丁叠补丁；字段无主人 |
| 假 COGS 凑「免费展示」 | 非强制；假成本更危险 |
| 删 brand 只留 `identifier_exists=no` | 装无主商品；对商家不友好 |
| 跟着外部 AI 打点改一整版 Feed | 审查 ≠ 需求 |
| 完整安检动画 / Magic Bar / 动态 URL 当主交付 | 北星已后置；内容质量未稳前做这些是偏航 |
| AI 去水印 / 白底当默认 | 已移出产品 |

---

## 4. 当前唯一正确的下一程（减层，不是加功能）

未完成前，**禁止**再开新审查修复、新 UX 大舱、新出口规则。

1. **标题减层：** 模型出骨架（禁尺码范围）→ 渲染只加本行 color、size 各一次。拆掉叠罗汉式 polish。  
2. **color / pattern 分家：** color 只写色；Style/花色进 pattern。  
3. **广告品牌：** App 确认；去掉静默 eprolo。  
4. **描述：** 一句卖点优先；尺码表缩短。  
5. **验收：** 固定三件真商品（裤/裙/夹克）购物标题「更短更好懂」；不用重复标题计数。

做完 1–4 再谈安检舱动效、抽屉、动态 URL。

---

## 5. 给协作者 / 其他 AI（改代码时）

> 你面前有很多 `docs/plans/*`。**先读北星 + 字段合同 + 本文。**  
> 若某份旧设计写「去水印 / 动态 URL 为主 / 出口再 polish 标题」——那是历史，不是当前需求。  
> 若审查报告要求删 brand、补假 COGS、把 Style 塞进 color——**拒绝**，指向字段合同。  
> **改代码前必答四问**（见字段合同 §4 / `.cursor/rules/feed-field-contract.mdc`）：主人是谁？修主人还是叠层？验收是购物标题还是打分？缺数据是算/填/编？  
> 已知债（`pin_variant_size`、脏 color、静默 eprolo）**只许拆不许加厚**。
