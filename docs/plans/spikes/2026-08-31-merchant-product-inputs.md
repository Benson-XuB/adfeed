# Spike: Merchant API productInputs（写推送）

**日期：** 2026-08-31  
**分支：** `feature/google-mc-issues`（或 `feature/google-api-push`）  
**结论：** Google 写路径用 Merchant API **`productInputs`**；**不用** Content API `custombatch`。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Design: docs/plans/2026-08-31-google-api-push-dual-export-design.md
```

---

## Insert URL

```
POST https://merchantapi.googleapis.com/products/v1/accounts/{account}/productInputs:insert?dataSource={dataSource}
```

- `{account}` — Merchant Center account id  
- `{dataSource}` — full resource name，如 `accounts/{id}/dataSources/{ds}`  
- **必须**指向 Input=API 的 dataSource（Primary 或 Supplemental）

---

## 约束

| 项 | 决定 |
|----|------|
| 写 API | `productInputs.insert` / `patch` / `delete` |
| 禁止 | Content API `custombatch`（已日落路径） |
| Scope | `https://www.googleapis.com/auth/content` |
| ID | `offerId` = Feed XML `<g:id>`（variant SKU） |
| 假值 | 不编 GTIN / 品牌 / 脏 color |

---

## 相关文档

- 设计规格：[`2026-08-31-google-api-push-dual-export-design.md`](../2026-08-31-google-api-push-dual-export-design.md)
- 实现计划：[`2026-08-31-google-api-push-dual-export.md`](../2026-08-31-google-api-push-dual-export.md)
- 只读 spike：[`2026-08-30-google-merchant-api-spike.md`](./2026-08-30-google-merchant-api-spike.md)
