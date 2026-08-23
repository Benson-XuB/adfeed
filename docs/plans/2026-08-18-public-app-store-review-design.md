# AdFeed AI — 公开 App Store 审查设计

**日期：** 2026-08-18  
**状态：** LOCKED（分发方式：公开商店）  
**Field contract:** `docs/plans/2026-08-14-feed-field-contract.md`  
**North Star:** `docs/plans/2026-08-12-mvp-north-star.md`

> 本文只解决 **Shopify 插件上架审查**。不改 Feed 字段主人（title/color/size/brand/GTIN）。不新增 pin 层、假码、静默 eprolo。

---

## 1. 目标

把现有嵌入式 App Home 交 **公开 Shopify App Store** 人工审查。评审员能在正式 HTTPS 上：安装 → 选商品 → 生成 Feed → 复制链接；计费走 Shopify；合规 webhook 返回正确状态码并在卸载 48h 后删除店铺数据。

**非目标：** Built for Shopify 徽章、主题扩展、受保护客户数据、write_products、保证 GMC 过审文案。

---

## 2. 锁定决策

| 项 | 选择 | 理由 |
|----|------|------|
| 分发 | 公开 App Store（非 unlisted） | 用户已拍板 |
| 生产域名 | `https://deltfu.com` | 已有服务器与 Nginx；toml 不得再交隧道 URL |
| 权限 | 继续只申请 `read_products` | 色/码写在我方 DB；改商品走 Shopify 深链 |
| 客户数据 | **不申请** Protected Customer Data | Feed 不碰买家/订单 |
| Admin API | 生产路径 **只走 GraphQL** | 2025-04-01 新公开 App 禁 REST |
| 计费 | 已有 Billing API：Free / Starter $14.99 / Growth $39 | 应用内升降级；生产 `test=false` |
| 隐私政策 | `https://deltfu.com/api/privacy` 静态页 | Listing 必填 URL（`/privacy` 目前被前端 Nginx 吃掉） |
| Sidekick | **先下线 FAQ 模板扩展** | `list_faqs` 与 Feed 产品不一致，条款 2.2.8 会拒 |

本地开发仍可用 Cloudflare 隧道，但 **提交审查的已发布版本** 必须指向 `deltfu.com`。

---

## 3. 架构

```
Shopify Admin (App Home, GraphQL Direct API)
        │  session token
        ▼
https://deltfu.com  FastAPI
        │  Admin GraphQL (access_token)
        ▼
Shopify Admin API
        │
webhooks ── HMAC ── app/uninstalled | products/* | subscriptions
                 └── compliance: customers/data_request|redact, shop/redact
```

- **卸载 `app/uninstalled`：** 立刻作废 token、取消计费状态、店铺标 inactive。**不立刻删库**（Shopify 规定 `shop/redact` 在卸载 48h 后才要求擦除）。
- **`shop/redact`：** 硬删该店 products/variants/jobs/feeds 文件/store 行。
- **`customers/*`：** 我方不存买家 PII → HMAC 通过后 200 + 审计日志即可；不得 401/500。

---

## 4. 审查会点的产品行为（保持现状即可）

- 嵌入 Admin，不手填店铺域名。
- 生成 Feed、待改色码、去 Shopify 编辑。
- Listing / 应用内 **禁止**「保证过 Google / 第一 / 唯一 / 转化率数字」。

---

## 5. 明确不做

- 改 title/color/size 生成逻辑  
- 申请更多 scope「以防万一」  
- 把 FAQ Sidekick 改造成半成品 Feed 工具（来不及对齐 listing）  
- 在 App 里用非 Shopify 收款  

---

## 6. 上线顺序

1. 生产 URL + GDPR 订阅 + HMAC + `shop/redact` 真删  
2. 隐私政策 / 支持页  
3. 应用内套餐升降级（生产 test=false）  
4. 服务端 REST → GraphQL  
5. 下线 app-tools FAQ；Listing 文案/图标/英文录屏  
6. 开发店：装 → 付费确认 → 生成 → 卸 → 再装；再提交审查  

实现任务见 `docs/plans/2026-08-18-public-app-store-review.md`。
