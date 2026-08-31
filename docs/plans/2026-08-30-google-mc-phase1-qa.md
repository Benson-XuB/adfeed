# Phase 1/2 QA — feature/google-mc-issues（未部署）

**分支：** `feature/google-mc-issues`  
**生产：** 不要 `shopify app deploy` / 不要改审核用服务器隐私，直到 App Store 审核结束。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Design: docs/plans/2026-08-31-google-api-push-dual-export-design.md
```

## 已实现（本分支）

- [x] Spike：Merchant + Ads  
- [x] Schema + purge  
- [x] offer 全等匹配 / issue→action / merchant sync（mock client）  
- [x] Ads metrics sync（mock）+ 降级标志  
- [x] API：`/api/app/google/*`（OAuth start 需 env；issues sync 可用 `mock_issues`）  
- [x] UI：`GmcIssuesPanel`「过审问题」  

## Google API push（沙盒 / 本分支）

- [ ] `GOOGLE_PUSH_ENABLED` gate — unset → push API 503；`=1` 才暴露推送  
- [ ] OAuth + dataSource select — 选 Merchant 后选/存 API 型 `data_source_name`  
- [ ] Push to Google (sandbox) CTA — UI 文案「推送到 Google（沙盒）」；非生产主路径  
- [ ] `offerId ==` XML `<g:id>` — 同源 canonical rows；抽样 SKU 全等  
- [ ] XML still generates (escape hatch) — Google XML 生成能力保留；沙盒不主推  
- [ ] No production `shopify.app.toml` / privacy / listing changes — 本分支 diff 为空或未改审核资产  

## 审核结束后再做

- [ ] 真实 Merchant HTTP client（替换 501）  
- [ ] OAuth callback 换 token 落库  
- [ ] 配置 `GOOGLE_OAUTH_*` + 隐私政策  
- [ ] Ads live `shopping_performance_view` + 商品级 UI 卡  
- [ ] 真实 MC 账号：`offer_id == Feed SKU` 抽样  

## 本地测

```bash
cd phase0 && .venv/bin/pytest tests/test_google_*.py tests/test_feed_field_fixes.py tests/test_mock_catalog*.py -q
```

确认：`git diff --stat phase0/add-feed-ai/shopify.app.toml` 无输出。
