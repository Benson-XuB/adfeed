# Spike: Merchant API productInputs Push

**日期：** 2026-09-07  
**状态：** 文档锁定；实机 OAuth+insert **未跑**（pending local spike）  
**Spec：** `docs/plans/2026-09-07-google-mc-push-design.md`

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. OAuth scope

```
https://www.googleapis.com/auth/content
```

官方：`productInputs.insert` Authorization scopes 写明此 scope。  
App 回调与营销站 `/api/public/google/oauth/*` **隔离**。

---

## 2. API primary data source（写入目标）

**规则：** 只有 **API 型** data source 能 `productInputs.insert`；不能写文件/URL 源。

### 创建（典型 REST）

```
POST https://merchantapi.googleapis.com/datasources/v1/accounts/{ACCOUNT_ID}/dataSources
```

最小 body（primary + API input）：

```json
{
  "displayName": "AdFeed",
  "primaryProductDataSource": {
    "channel": "ONLINE_PRODUCTS",
    "countries": ["US"],
    "contentLanguage": "en",
    "feedLabel": "US"
  }
}
```

> 实现时以官方 [Manage API data sources](https://developers.google.com/merchant/api/guides/data-sources/api) / `accounts.dataSources.create` 为准；以 200 响应里的 `name` 为准。

### 列表 / 复用

```
GET https://merchantapi.googleapis.com/datasources/v1/accounts/{ACCOUNT_ID}/dataSources
```

找 `displayName == "AdFeed"` 且为 API primary；有则复用 datasource id。

---

## 3. productInputs.insert

**文档：** https://developers.google.com/merchant/api/reference/rest/products_v1/accounts.productInputs/insert

```
POST https://merchantapi.googleapis.com/products/v1/accounts/{ACCOUNT_ID}/productInputs:insert
    ?dataSource=accounts/{ACCOUNT_ID}/dataSources/{DATASOURCE_ID}
```

同 `contentLanguage` + `offerId` + `dataSource` 再 insert → **替换**。处理后可能数分钟才可 `products.get`。

### ProductInput 最小字段（V1）

见 `phase0/adfeed/google_mc_push/mapping.py`。要点：

| Feed / 行 | API |
|-----------|-----|
| `sku` / `<g:id>` | `offerId` |
| `identifier_exists=no` | `identifierExists: false`；不写 gtins |
| 真 GTIN | `gtins: ["..."]`（绝不编造） |
| `price` + `currency` | `price.amountMicros` + `currencyCode` |
| `in_stock` | `IN_STOCK` |
| `image_url` / `image_link` | `imageLink` |
| `size` | `sizes: ["M"]` |

---

## 4. offerId ↔ Feed `<g:id>`

XML：`<g:id>{{ p.sku }}</g:id>`。  
**锁定：** `offerId` = 生成行 `sku`。

---

## 5. 实机验证

| 项 | 状态 |
|----|------|
| OAuth + create data source + insert 1 SKU + MC UI | **未跑** — pending local spike |

---

## 6. 实现注意

- V1 成功 = insert 200；不等 approved  
- 不写文件型源；不编 GTIN；排除 ≠ delete  
