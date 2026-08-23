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
| Category | Marketing |
| Secondary / tags | Product feeds, Google Shopping, catalog |
| Not a tag | Sales channel |
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

### Subtitle (app card)

```
Generate Google Shopping feeds from your Shopify catalog.
```

### App introduction (card / search snippet)

```
Turn your catalog into a shopping feed and copy a persistent URL into Merchant Center.
```

### App details

```
AdFeed AI builds a shopping feed from your catalog.

Confirm ad brand, pick a target country, select products, then generate. It structures shopping titles, flags missing color/size, and gives a persistent feed URL in the embedded App Home.

It does not invent barcodes or cost. Add a real UPC/EAN in Shopify if you have one; otherwise use the no-ID path.

This app does not guarantee Google Merchant Center approval. Limited/pending after submit is usually Google’s initial review.
```

### Features (3–5 lines)

```
Confirm your ad brand, then generate a shopping feed
Flag missing color and size so you can fix each variant
Copy a persistent feed URL into Merchant Center
Change plan in the app and approve the Shopify charge
Embedded App Home for brand, markets, and feed links
```

### Pricing details (only place prices belong)

```
Plans are billed through Shopify. Change plan in App Home without reinstalling.

Free: 20 generate units per month.
Starter: $14.99 USD per month, 150 generate units.
Growth: $39 USD per month, 400 generate units.

One generate uses one unit per selected SKU × selected market. Unused units do not roll over. Approve or decline the Shopify charge to change plan. Reinstalling asks for charge approval again.
```

### Search terms

```
google shopping feed, product feed, merchant center, shopping ads, catalog feed
```

---

## 3. Chinese listing (zh-CN)

### 副标题

```
从 Shopify 商品目录生成 Google 购物 Feed。
```

### 简介

```
把目录做成购物 Feed，复制长期有效的链接到 Merchant Center。
```

### 详情

```
AdFeed AI 用你店里已有的 Shopify 商品生成购物广告 Feed。

先确认广告品牌，选择目标国家，勾选商品后生成。应用会整理购物标题、标出缺色缺码方便你改，并给出可粘贴到 Merchant Center 的 Feed 链接。

尚未纳入 Feed 的商品，保存缺色/缺码时会写回 Shopify 变体的 Color/Size（`write_products`）；已在 Feed 内的修复只更新 Feed 数据库。不会改标题、价格或图片。

颜色只写颜色，尺码只写尺码。不会编造条码或成本。有真实 UPC/EAN 请在 Shopify 变体上填写；没有就走无码路径。

不保证 Google Merchant Center 过审。提交后 Limited / Pending 通常是 Google 初审队列。
```

### 功能点

```
确认广告品牌后生成购物 Feed
标出缺色、缺码，方便按变体修改
复制长期有效的 Feed 链接到 Merchant Center
在应用内切换套餐，并在 Shopify 确认扣费
嵌入式 App Home：品牌、市场与 Feed 链接
```

### 价格说明

```
通过 Shopify 计费。在应用首页切换套餐，无需重装。

免费：每月 20 个生成单位。
Starter：每月 14.99 美元，150 个生成单位。
Growth：每月 39 美元，400 个生成单位。

一次生成消耗「所选 SKU × 市场」个单位。未用完不结转。升降级在 Shopify 确认扣费即可。
```

---

## 4. URLs (listing form)

Use the `/api/` paths. The site root `/privacy` is served by the frontend and has returned 502; FastAPI serves `/api/privacy` and `/api/support`.

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
| App icon | `icon-1200.png` | 1200×1200 PNG. No Shopify mark. No prices. |
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
