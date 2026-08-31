# AdFeed AI Marketing Landing — Design Spec

**日期：** 2026-09-01  
**状态：** ACCEPTED（英文为主；首页长滚动含完整 How-to；静态站方案 A）  
**隔离：** 只改 `landing-page/`；**禁止** `shopify app deploy` / 改审核生产 App

```
North Star: docs/plans/2026-08-12-mvp-north-star.md
Listing: docs/app-store-listing/FILL-ENGLISH-LISTING.md
```

## 决议

| 项 | 选择 |
|----|------|
| 语言 | 英文为主 |
| 形态 | 重做静态站 `landing-page/` |
| How-to | 首页长滚动完整 6 步 |
| 卖点范围 | **main / App Store V1.0** 能力；不主推沙盒 API 推送 / Ads 指标 |

## 页面

- `index.html` — Hero, audience, features, how-to ×6, never-do, pricing, footer  
- `privacy.html` / `terms.html` / `support.html`  
- Shared `styles.css`（或拆 `legal.css`）

## 视觉

- 明亮纸白 + 深墨 + 氧化绿强调；非暗黑霓虹、非紫渐变  
- 字体：品牌展示 Fraunces；正文 Source Sans 3  
- Hero 全宽氛围，首屏仅品牌+headline+一句+CTA  
- 真截图：`docs/app-store-listing/screenshots/`

## How-to 六步

1. Install AdFeed AI  
2. Confirm ad brand（非 1688 供应商名）  
3. Choose market  
4. Select products（可选色码/主图）  
5. Generate feed → persistent URL  
6. Paste URL into Google Merchant Center as scheduled data source  

## 联系

- Support: support@deltfu.com  
- Privacy/Support URLs 可与现网 `deltfu.com/api/*` 并存；静态站自包含法律页  

## 非目标

- 部署到生产 / 改 Partner listing  
- 承诺过审、代投  
- 中文主站（可后加）  
