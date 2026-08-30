# Spike: Meta Catalog — 连接 + 挂 Feed（只读/发布目录）

**日期：** 2026-08-30  
**分支：** `feature/google-mc-issues`（multi-platform 同枝）  
**结论：** 用 Marketing API / Graph **Product Catalog + Product Feed**；OAuth 权限 `catalog_management`（+ 列 Business 时 `business_management`）；P2 优先 **schedule 拉取已生成的 Meta Feed URL**，不 Bulk 编造字段。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. API 选择

| 能力 | 端点方向 |
|------|----------|
| 列 Catalog | `GET /{business-id}/owned_product_catalogs` 或用户可达 catalogs |
| 创建/挂 Feed | `POST /{catalog-id}/product_feeds` + `schedule.url` = AdFeed 公开 Meta XML |
| 触发抓取 | `POST /{product-feed-id}/uploads`（可选手动） |

官方：

- [Catalog get started](https://developers.facebook.com/docs/marketing-api/catalog/get-started/)
- [Feed API](https://developers.facebook.com/docs/marketing-api/catalog/guides/feed-api/)

Graph 版本实现默认 `v21.0`（可用 `META_GRAPH_VERSION` 覆盖）。

---

## 2. OAuth

授权：`https://www.facebook.com/{version}/dialog/oauth`  
换票：`https://graph.facebook.com/{version}/oauth/access_token`

建议 scope（空格分隔）：

```
catalog_management business_management
```

长期 token：短期 user token → `fb_exchange_token` 换 long-lived；存封存后的 token（列名 `access_token_enc`，Meta 常无独立 refresh）。

Env：

```
META_APP_ID=
META_APP_SECRET=
META_OAUTH_REDIRECT_URI=https://…/api/app/meta/oauth/callback
```

---

## 3. 与 AdFeed Feed 对齐

| AdFeed | Meta |
|--------|------|
| `platforms/meta/feed.py` RSS（无 `g:`） | Catalog feed XML |
| `<id>` = variant SKU | retailer_id / id |

禁止为过审编假 GTIN/品牌。

---

## 4. P2 范围

- [x] 设计/spike  
- [ ] OAuth 起止 + 存 token  
- [ ] 列/选 Catalog  
- [ ] 将当前店 Meta Feed URL 挂到选中 Catalog 的 product_feed schedule  
- [ ] App `MetaCatalogPanel`  

**不做（P4）：** item issues 拒审同步。

**本机未换真实 Meta App token**（审核期不部署生产 OAuth）。
