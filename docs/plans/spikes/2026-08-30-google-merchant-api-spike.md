# Spike: Google Merchant API — 过审问题（只读）

**日期：** 2026-08-30  
**分支：** `feature/google-mc-issues`  
**结论：** Phase 1 用 **Merchant API**（勿新接即将日落的纯 Content API 写路径）；OAuth scope：`https://www.googleapis.com/auth/content`

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. API 选择

| 选项 | 用途 | 决策 |
|------|------|------|
| **Merchant API** `accounts.products` / Reports `product_view` | 读 `productStatus`、`itemLevelIssues`、`offer_id` | **采用** |
| Content API for Shopping | 旧栈；与 `auth/content` 同源 | 仅作兼容理解，新代码走 Merchant |
| `issueresolution.renderproductissues` | 第三方 UI 可渲染的拒审文案 | **P1.5 可选**（先存 code + 官方 description） |

官方指南：

- [List products data and product issues](https://developers.google.com/merchant/api/guides/products/list-products-data-issues)
- [Evaluate products / product_view](https://developers.google.com/merchant/api/guides/reports/evaluate-products)
- Scope 例：issueresolution 文档要求 `https://www.googleapis.com/auth/content`

---

## 2. OAuth scope（精确）

```
https://www.googleapis.com/auth/content
```

Phase 1 **只请求该 scope**。Ads 用增量授权另加 `adwords`（见 Ads spike）。

---

## 3. 读问题的推荐路径（实现顺序）

### Path A（同步列表，简单）

`products.list` / `products.get` → 读 `productStatus.itemLevelIssues[]`、`destinationStatuses[]`。

Issue 字段关注：

- `code` → 我方 `reason_code`
- `severity` → `DISAPPROVED` / `DEMOTED` / `NOT_IMPACTED` → 映射 UI 状态
- `attribute` → 提示改哪个 Feed 属性（不自动写假值）
- `description` / resolution 文案 → `reason_text`

### Path B（按拒审过滤，适合「过审问题」列表）

`accounts.reports.search` + MCQL，例如：

```sql
SELECT id, offer_id, feed_label, title,
       aggregated_reporting_context_status, item_issues
FROM product_view
WHERE aggregated_reporting_context_status = 'NOT_ELIGIBLE_OR_DISAPPROVED'
```

**P1 实现建议：** 先 Path B 拉「有问题的商品」，再用 Path A/`item_issues` 填详情；客户端接口抽象为 `list_product_issues(merchant_id) -> list[IssueDict]`，便于 mock。

---

## 4. ID 对齐（与 AdFeed Feed）

| 来源 | 字段 |
|------|------|
| 我方 Feed XML | `<g:id>` = **variant SKU**（`feed_generator.py`） |
| Merchant | `offer_id`（Reports / Product） |

**对齐规则（已写入实现）：** 字符串**全等**匹配 SKU；对不齐进「未匹配」桶，禁止模糊绑定。

本地未跑真实 OAuth；合入生产前用一台已挂 Feed 的 MC 账号验证 `offer_id == SKU`。

---

## 5. 阻塞 / 上线前检查

- [ ] Google Cloud 项目启用 Merchant API  
- [ ] OAuth 同意屏幕加 `auth/content`  
- [ ] 测试 refresh token 能 `reports.search`  
- [ ] 真实 `offer_id` 与 Feed SKU 抽样 10 条  

**本 spike 未在本机换真实 token**（审核期不接生产）。
