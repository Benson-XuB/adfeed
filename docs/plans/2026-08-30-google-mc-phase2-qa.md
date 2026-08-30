# Phase 2 QA — Ads 商品级效果（只读）

**分支：** `feature/google-mc-issues`  
**环境：** 本地 / 预览；**勿**在 App Store 审核中的生产强制用户授权。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## 前置

- [ ] `GOOGLE_OAUTH_*` + `GOOGLE_ADS_DEVELOPER_TOKEN` 已配（可另加 `GOOGLE_ADS_LOGIN_CUSTOMER_ID` 经理户）
- [ ] 同意屏幕含 `auth/adwords`
- [ ] 测试 CID 有 Shopping / PMax 近 7 日流量

## 清单

1. [ ] 「过审问题」已连 Google 后，「广告效果」显示「授权读取 Ads」
2. [ ] 增量授权成功 → `has_ads_scope`
3. [ ] 填入 Ads customer ID → 同步 → 有商品级行时展示 offer / SKU
4. [ ] 无商品级时出现降级文案（系列汇总）
5. [ ] 断开 Google 后 metrics 缓存被清

## 不做

- 改出价 / 建系列 / 自动 mutate Ads
