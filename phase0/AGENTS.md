# AdFeed phase0 — Agent 改代码须知

改 Feed / 标题 / 属性 / 质量门 / App 生成相关代码前，**先读**：

1. `docs/plans/2026-08-12-mvp-north-star.md` — 做什么  
2. `docs/plans/2026-08-14-feed-field-contract.md` — 怎么改字段（禁止出口打补丁）  
3. `docs/plans/2026-08-14-design-audit-cleanup.md` — 哪些旧设计已废  

会话规则：`.cursor/rules/feed-field-contract.mdc`（alwaysApply）。

**一句话：** 修字段主人；不要在 `feed_generator` / `title_guard` 再叠一层；购物标题要像衣服，不要跟着审查清单打补丁。
