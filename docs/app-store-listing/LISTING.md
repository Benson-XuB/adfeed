# Shopify App Store listing pack (paste-ready)

Field contract: `docs/plans/2026-08-14-feed-field-contract.md`  
North Star: `docs/plans/2026-08-12-mvp-north-star.md`

This pack is for **Partner Dashboard → Distribution → App Store listing**. It does not change Feed field owners (title / color / size / brand / GTIN).

Upload files from this folder. Do not upload scene HTML.

---

## 1. App identity

| Field | Paste |
|---|---|
| App name | AdFeed AI |
| Languages | English (primary), Chinese (Simplified) |
| Category | **Sales channels → Selling online → Product feeds** |
| Secondary / tags | （若允许）仅当表单另有相关 tag；主功能仍是 Product feeds |
| Not a tag | 不要选 Dropshipping / Ads / Retail |
| Protected customer data | **Opt out** (app does not read customers or orders) |
| Access scopes shown to merchants | `read_products`, `write_products`, `read_legal_policies` |

### Why these scopes

| Scope | Used for |
|---|---|
| `read_products` | Sync catalog to build shopping feeds |
| `write_products` | When you save a missing color/size on a product **not yet in the feed** — updates that variant's Color/Size option in Shopify. Never changes title, price, images, or other fields. Products already in the feed: fixes stay in the feed database. |
| `read_legal_policies` | Read store policy pages (returns/refunds) for compliance hints in App Home |

---

## 2. English listing (primary)

> **定位：** 专为 **1688 导入 Shopify 的商品** 优化并生成 Google data feed。  
> 粘贴主文档：`FILL-ENGLISH-LISTING.md`

### Subtitle (app card, ≤62)

```
Google Shopping feeds for 1688-imported product catalogs.
```

### App introduction (≤100) — **不得含单词 Shopify**

```
Turn 1688-imported products into a Google Shopping feed.
```

### App details (≤500)

```
AdFeed AI is built for online stores that import products from 1688.

Confirm an ad brand (not the 1688 supplier name), pick a country, select products, then generate. Get clearer shopping titles, optional color/size tips, and a persistent Google Merchant Center feed URL.

Does not invent barcodes or cost. No GTIN? Use the no-ID path. Does not guarantee Merchant Center approval.
```

### Features (≤80 each)

```
Built for 1688 products imported into your store
Confirm ad brand so 1688 supplier names are not your Google brand
Optional color and size tips before you generate the feed
Copy a persistent feed URL into Google Merchant Center
Pick products and choose the image used in your Google feed
```

### Pricing details (only place prices belong)

```
Plans are billed in Admin. Change plan in App Home without reinstalling.

Free: 3 generate units per month.
Starter: $14.99 USD per month, 50 generate units.
Growth: $39 USD per month, 200 generate units.

One generate uses one unit per selected SKU × selected market. Unused units do not roll over. Approve or decline the billing charge to change plan.
```

### Search terms (5)

```
1688
google shopping feed
product feed
catalog feed
merchant center
```

---

## 3. Chinese listing (zh-CN)

### 副标题

```
为导入 Shopify 的 1688 商品生成 Google 购物 Feed。
```

### 简介

```
把 1688 导入 Shopify 的商品优化成 Google 购物 Feed。
```

### 详情

```
AdFeed AI 专为把 1688 商品导入 Shopify 的店铺，优化并生成 Google 购物广告 Feed（Google data feed）。

先确认广告品牌（不要用 1688 供应商名当 brand），选择目标国家，勾选商品后生成。整理更易读的购物标题，可选提示缺色缺码，并给出可粘贴到 Merchant Center 的长期 Feed 链接。

颜色只写颜色，尺码只写尺码。不会编造条码或成本。有真实 UPC/EAN 请在 Shopify 变体上填写；没有就走无码路径。

不保证 Google Merchant Center 过审。提交后 Limited / Pending 通常是 Google 初审队列。
```

### 功能点

```
专为 1688 导入 Shopify 的商品优化 Feed
确认广告品牌，避免 1688 供应商名写成 Google brand
生成前可选提示缺色、缺码
复制长期有效的 Feed 链接到 Merchant Center
勾选商品并选择用于 Google Feed 的商品主图
```

### 价格说明

```
通过 Shopify 计费。在应用首页切换套餐，无需重装。

免费：每月 3 个生成单位。
Starter：每月 14.99 美元，50 个生成单位。
Growth：每月 39 美元，200 个生成单位。

一次生成消耗「所选 SKU × 市场」个单位。未用完不结转。升降级在 Shopify 确认扣费即可。
```

---

## 4. URLs (listing form)

Use the `/api/` paths (FastAPI). Root `/privacy` and `/support` also work via nginx → API, but listing should keep the stable `/api/` URLs.

| Field | URL |
|---|---|
| Privacy policy | https://deltfu.com/api/privacy |
| Support / FAQ | https://deltfu.com/api/support |
| App URL (already in toml) | https://deltfu.com |
| Support email | support@deltfu.com |

Emergency developer contact: same inbox `support@deltfu.com`. Phone is not used; reviewers should email.

---

## 5. Media to upload

| Slot | File | Notes |
|---|---|---|
| App icon | `icon-1200-v2.png` (preferred) or `icon-1200.png` | 1200×1200 PNG. No Shopify mark. No prices. |
| Screenshot 1 | `screenshots/01-confirm-brand.png` | Confirm brand → Generate feed |
| Screenshot 2 | `screenshots/02-product-list.png` | Product list, Edit this in Shopify |
| Screenshot 3 | `screenshots/03-fix-size.png` | Missing size / Add size |
| Screenshot 4 | `screenshots/04-copy-url.png` | Copy persistent feed URL |
| Feature media | `screenshots/05-ad-image.png` | Pick ad image (unique view) |
| Screencast | `screencast/adfeed-ai-screencast.mp4` | English captions, ~75s. Upload unlisted to YouTube/Loom, paste URL. |

Do **not** upload `screenshots/06-change-plan.png` to the listing gallery (billing UI). It is only a screencast slide. Listing images must not show prices; that slide also avoids dollar amounts.

---

## 6. Partner Dashboard toggles

- Distribution: **Public App Store**
- Built for Shopify: leave unchecked
- Theme app extension: none
- Webhooks / GDPR: already in `shopify.app.toml` (`customers/data_request`, `customers/redact`, `shop/redact`)
- Direct API: Admin GraphQL (online)

---

## 7. Testing instructions

Paste the entire contents of `TESTING.md` into the review form testing-instructions field.
