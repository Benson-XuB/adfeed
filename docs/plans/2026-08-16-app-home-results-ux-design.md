# 2026-08-16 App Home 生成后结果页 UX（方案 1）

Field contract: docs/plans/2026-08-14-feed-field-contract.md  
North Star: docs/plans/2026-08-12-mvp-north-star.md

## Goal

生成 Feed 后，商家用三幕看懂并改完：链接 → 需确认商品（标题+图）→ 摘要/技术细节折叠。一件改：勾选 → 填色/码 → 一次应用（不扣优化配额）。

## Non-goals

不改 Feed 字段主人；不假写 GTIN/品牌；不做 Magic Bar；主页选品区留第二刀。

## Information architecture

1. **交给 Google** — 平台/市场/条数 + URL + 复制 + Limited 一句  
2. **需要你看一眼** — Multicolor / One Size / 敏感 / 主图；行展示缩略图+标题；顶部 sticky 一件改条  
3. **本轮摘要** — 自动/抽查/高风险一行；优化日志与 `g:*` 表默认折叠  

流水线五步跑完默认折叠。

## Constraints

Shopify Polaris Web Components only.
