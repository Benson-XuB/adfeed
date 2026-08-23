# AdFeed AI — MVP 北星目标（锁定，不可漂移）

**日期：** 2026-08-12  
**状态：** **LOCKED** — 所有新功能、重构、技术选型必须先对照本文  
**权威级别：** 高于各子模块设计文档；与子文档冲突时 **以本文为准**

---

## 一句话北星

> **让 1688 → Shopify 商家的 Google Shopping Feed 在上架前尽量可过审：**  
> **Feed 质量（字段/标题/属性/价币种/敏感词） + 主图选择（用户自选，不修图） + 过审闭环（检测 → 报告 → 可改 → 再生成）。**

**不是 MVP 胜负手的，一律后置或明确不做。**

---

## 三大支柱（MVP 只认这三件事）

| 支柱 | 含义 | 验收标准 |
|------|------|----------|
| **① Feed 质量** | 生成时字段齐全、GMC 机审习惯、可解释的质量报告（AUTOFIX / WARN / FATAL） | 商家能在 App 里看见「修了什么、还缺什么」；价币种与落地页一致；服装属性/无码通道/敏感词已覆盖 |
| **② 主图选择** | 从 Shopify 商品已有图库 **推荐 + 用户自选** Feed 主图；**不做 AI 去水印** | I03 检测脏图域名；per-SKU 换图写 `feed_image_url`；不重写 Shopify 主图 |
| **③ 过审闭环** | 上 Google **之前** 完成：生成 → 质量报告 → 网站合规轻诊断 → 用户确认/修正 → 再生成 Feed | 不承诺 100% 过审，但路径闭环、问题可见、可迭代 |

三者关系：

```
1688 脏数据 → Shopify 店铺
       ↓
  [① Feed 质量引擎]  标题/属性/价/敏感词/链接
       ↓
  [② 主图选择]       推荐干净图，用户点选
       ↓
  [③ 过审闭环]       报告 + 修正 + 再生成 → 投广告
```

---

## 明确后置（不是现在不做，是 **不是 MVP 胜负手**）

以下能力 **可以存在于 backlog**，但 **不得占用 MVP 主线精力**，不得作为重构理由：

| 类别 | 后置项 | 理由 |
|------|--------|------|
| **图片** | AI 去水印、白底、OCR、场景图、短视频 | 成本高、过审不确定；主图自选更稳（见 `2026-08-12-feed-image-picker-mvp.md`） |
| **架构** | Celery / Redis 队列、高并发、微服务拆分 | 初期用户少；`threading` + job 轮询够用 |
| **架构** | 迁 Remix + Polaris React | 当前 Admin UI Extension + `s-*` 组件已是官方路线，观感原生 |
| **架构** | 单次硬限 5 SKU、强制同步 HTTP（去掉 job） | 等有真实超时/并发反馈再议；现在不改 |
| **UX 大工程** | 完整安检舱动画、大型批量抽屉、动态 Feed URL 为主交付 | 保证 **Feed 内容质量** 优先；下载/XML 可验收 |
| **供应链** | 1688 选厂、B2B 阶梯价、批发词引擎 | 非广告 Feed 过审核心 |
| **链接** | Query 白名单清洗 | 已 DEFER（见 `2026-08-11-feed-link-allowlist-deferred.md`） |

---

## 技术栈锁定（MVP 阶段不预防性重构）

| 层 | 锁定选型 | 说明 |
|----|----------|------|
| App UI | Preact + **Shopify Admin UI Extension** + Polaris **Web Components**（`s-page`, `s-button`…） | 不是 `@shopify/polaris` React；**不迁** |
| 生成任务 | FastAPI + DB `store_jobs` + 后台 `threading` + 前端 `pollJob` | 不是 Celery/Redis |
| Shopify 鉴权 | Session JWT → 官方 token exchange → store `access_token` | 不手写 cookie session |
| 图片 | `feed_image_url` override + `classify_image_risk` 启发式 | 万相 API **无产品入口** |

---

## 新需求准入三问（写代码 / 写文档前必答）

1. **是否直接提升 ① Feed 质量、② 主图选择、或 ③ 过审闭环？**  
   - 若否 → 默认 **不做** 或 **defer**，除非用户显式要求且接受 scope 漂移风险。

2. **是否让商家在上 Google 前更容易发现并修正拒审风险？**  
   - 若否 → 优先级低于三大支柱。

3. **是否引入新基础设施（队列、新框架、新 OAuth 方案）？**  
   - 若是 → **需要书面理由 + 真实痛点数据**；默认拒绝。

4. **改 Feed 内容时：是改字段主人，还是又在出口打补丁？**  
   - 对照 `2026-08-14-feed-field-contract.md`。出口再叠一层（钉 Size、把 Style 塞进 color）→ **默认拒绝**。购物卡可读性优先于外部审查打分。

---

## 子文档索引（均须服从本文北星）

| 文档 | 与北星关系 |
|------|------------|
| `2026-08-10-high-quality-feed-engine-design.md` | ① Feed 质量 + ③ 闭环（S1/S6；S7 已收敛为主图选择） |
| `2026-08-12-feed-image-picker-mvp.md` | ② 主图选择（锁定 scope） |
| `2026-08-12-store-website-compliance-lite.md` | ③ 过审闭环（投广告前网站诊断） |
| `2026-08-11-sensitive-compliance-p0/p1.md` | ① Feed 质量（护号） |
| `2026-08-09-price-currency-markets-design.md` | ① Feed 质量（价币种） |
| `2026-08-09-feed-quality-gate-design.md` | ① + ③ 质量门 |
| `2026-08-10-adfeed-requirements-inventory.md` | 全量需求池；**实现优先级以本文为准** |
| `2026-08-14-feed-field-contract.md` | ① **怎么改 Feed**：字段主人、禁止出口打补丁；与审查清单冲突时以该合同为准 |
| `2026-08-14-design-audit-cleanup.md` | **设计盘点**：哪些文档仍有效 / 已过期 / 易误导；冲突时服从本文 + 字段合同 |

---

## 修订规则

- **修改本文** 需产品负责人明确拍板（口头「换个方向」不算）。  
- 子模块文档可细化实现，**不得重新定义 MVP 北星**。  
- 每次大功能 PR / 计划文档开头应写：  
  `North Star: docs/plans/2026-08-12-mvp-north-star.md`  
  `Field contract: docs/plans/2026-08-14-feed-field-contract.md`

---

## 给未来协作者 / 其他 AI 的一句话

> AdFeed MVP 的胜负手是 **Feed 过审闭环**，不是技术栈炫技。  
> 别建议迁 Polaris React、别建议上 Celery、别建议默认 AI 修图——除非北星文档已被正式修订。
