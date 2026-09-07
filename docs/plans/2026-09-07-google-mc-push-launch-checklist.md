# Google MC Push — 过审后上线清单

**Spec：** `docs/plans/2026-09-07-google-mc-push-design.md`  
**Plan：** `docs/plans/2026-09-07-google-mc-push.md`

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## Cloud / env

- [ ] OAuth Client 增加 App redirect：`https://deltfu.com/api/app/google/oauth/callback`
- [ ] 本地调试 URI：`http://127.0.0.1:8000/api/app/google/oauth/callback`
- [ ] 生产 `.env`：`GOOGLE_OAUTH_CLIENT_ID/SECRET`、`GOOGLE_APP_OAUTH_REDIRECT_URI`、`SHOPIFY_APP_HANDLE`
- [ ] Test users 含试用邮箱（若 OAuth 仍为 Testing）

## 代码 / 部署

- [ ] 合并 `feature/google-mc-push`（或等价 main 上 MC Push commits）— **审核中勿改生产 listing/隐私 Google 文案**
- [ ] 部署 API（含 `phase0/adfeed/google_mc_push/`）
- [ ] 嵌入式 App 构建含 Push CTA（Task 2.1）

## 验收

- [ ] 测试店：Generate → Connect Google → 选 MC → Push
- [ ] Merchant Center **AdFeed API** 源下出现对应 `offerId`（pending 可）
- [ ] 结果页成功/失败计数正确；排除 SKU 未推送
- [ ] 文案含「不保证 Google 批准」
- [ ] App Home / 审核面无回归

## 明确不做（上线时仍遵守）

- 不写文件型 data source  
- 不编 GTIN  
- 不等 approved  
- V1 不自动 delete  
