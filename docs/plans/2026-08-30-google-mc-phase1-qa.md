# Phase 1/2 QA — feature/google-mc-issues（未部署）

**分支：** `feature/google-mc-issues`  
**生产：** 不要 `shopify app deploy` / 不要改审核用服务器隐私，直到 App Store 审核结束。

## 已实现（本分支）

- [x] Spike：Merchant + Ads  
- [x] Schema + purge  
- [x] offer 全等匹配 / issue→action / merchant sync（mock client）  
- [x] Ads metrics sync（mock）+ 降级标志  
- [x] API：`/api/app/google/*`（OAuth start 需 env；issues sync 可用 `mock_issues`）  
- [x] UI：`GmcIssuesPanel`「过审问题」  

## 审核结束后再做

- [ ] 真实 Merchant HTTP client（替换 501）  
- [ ] OAuth callback 换 token 落库  
- [ ] 配置 `GOOGLE_OAUTH_*` + 隐私政策  
- [ ] Ads live `shopping_performance_view` + 商品级 UI 卡  
- [ ] 真实 MC 账号：`offer_id == Feed SKU` 抽样  

## 本地测

```bash
cd phase0 && .venv/bin/pytest tests/test_google_*.py -v
```
