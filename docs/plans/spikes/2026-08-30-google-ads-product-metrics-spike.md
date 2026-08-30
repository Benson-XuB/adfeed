# Spike: Google Ads — 商品级效果（只读）

**日期：** 2026-08-30  
**分支：** `feature/google-mc-issues`  
**结论：** 商品级用 `shopping_performance_view`；OAuth **仅有** scope `https://www.googleapis.com/auth/adwords`（无更窄只读 scope）→ **应用层只调用 Search/SearchStream，绝不 mutate**。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. 资源

- [`ShoppingPerformanceView`](https://developers.google.com/google-ads/api/reference/rpc/v24/ShoppingPerformanceView)  
  Shopping / PMax 在**商品维度**的展示、点击等；与系列报表数字可能不一致（官方说明：按「广告里露出的商品」计）。

GAQL 方向（实现时按当前 API 版本改字段名）：

```sql
SELECT
  segments.product_item_id,
  metrics.impressions,
  metrics.clicks,
  metrics.cost_micros,
  metrics.conversions
FROM shopping_performance_view
WHERE segments.date DURING LAST_7_DAYS
```

`segments.product_item_id` 通常对应 Merchant **offer id** / 商品 id → 与 Feed SKU / `offer_id` 再全等对齐。

---

## 2. OAuth scope

```
https://www.googleapis.com/auth/adwords
```

另需：**Developer Token**、OAuth client、客户 CID；经理户访问时带 `login-customer-id`。

**增量授权：** Phase 1 只要 `auth/content`；用户点「连接广告」再请求 `adwords`。

---

## 3. 降级策略（决议 4B）

| 情况 | UI |
|------|-----|
| 有 `shopping_performance_view` 行且 `product_item_id` 非空 | 展示商品级花费/点击 |
| API 错误 / 无 Shopping 系列 / 空商品维 | 降级账户或系列汇总，文案：「本账号暂无商品级数据」 |
| 未授权 Ads | 灰显连接，不影响「过审问题」 |

---

## 4. 上线前检查

- [ ] Ads API 开发者令牌（测试/正式）  
- [ ] 同意屏幕增加 `adwords`  
- [ ] 一台有 Shopping 流量的 CID 验证 `product_item_id` 与 Feed SKU  
- [ ] 隐私政策写明只读 Ads 效果  

**本 spike 未换真实 Ads token。**
