# Phase 4 QA — Meta / TikTok 拒审只读

**分支：** `feature/google-mc-issues`  
**勿**在审核中的生产强制授权。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## Meta

1. [ ] 连接 + 选 Catalog 后「同步拒审问题」有行或空态不报错  
2. [ ] offer_id 与 Feed SKU 全等匹配；未匹配单独标记  
3. [ ] 建议动作仅映射现有能力（图/色码/品牌/只读）  

## TikTok

1. [ ] 连接 + 选 Shop 后「同步上架问题」；API 无 diagnoses 时允许空列表  
2. [ ] 同样全等匹配 SKU；不编造字段  

## 共用

1. [ ] Disconnect / shop redact 清 issues 表  
2. [ ] 与 Google「过审问题」面板并列，代码不糊在一个 client 里  
