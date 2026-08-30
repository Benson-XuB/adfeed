# Spike: TikTok Shop — 连接 + 挂 Feed

**日期：** 2026-08-30  
**结论：** 用 **TikTok Shop Partner** OAuth（非普通 Login Kit）；列 Shop；本店已生成的 **CSV** 经公开 URL 交给商家/后续 Products API。Shop **没有** Meta 同款「按 URL 定时抓 XML」——P3 以 **登记 Feed URL + 选 Shop** 为主，批量建品推送留后续。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. API 选择

| 能力 | 方向 |
|------|------|
| OAuth | Partner `auth.tiktok-shops.com` authorize + `api/v2/token/get` / refresh |
| 列店铺 | `GET /authorization/202309/shops`（需 Access-Token + app 签名） |
| 目录 | 我方 `platforms/tiktok/feed.py` CSV；**不编造重量** |
| 「挂 Feed」P3 | 将 durable CSV URL 记到 `tiktok_shops.feed_url`；UI 可复制。真正 `product/202309/products` 逐条推送 = 后续迭代 |

Ads Catalog Feed（`open_api/v1.3/catalog/feed`）是广告目录，**不是** Shop 卖货主路径；本 Spec 不做。

---

## 2. OAuth / Env

```
TIKTOK_CLIENT_KEY=
TIKTOK_CLIENT_SECRET=
TIKTOK_OAUTH_REDIRECT_URI=https://…/api/app/tiktok/oauth/callback
TIKTOK_API_BASE=https://open-api.tiktokglobalshop.com
```

Scope 以 Partner Center 勾选的商品/授权权限为准（实现存服务端返回的 scope 字符串）。

---

## 3. 与 Feed 对齐

| AdFeed | TikTok |
|--------|--------|
| CSV `Variant ID` | SKU |
| `Product ID` | item_group_id |
| Weight / package | **仅透传**；缺则空（字段合同） |

---

## 4. P3 范围

- OAuth 起止、封存 refresh/access  
- 列/选 Shop  
- attach：登记公开 CSV URL  
- `TikTokShopPanel`  

**不做：** 拒审同步（P4）；逐 SKU Products API  bulk 创建。

**本机未换真实 Partner App token。**
