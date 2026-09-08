# 闭环 handoff（2026-09-08）

本地 `shopify app dev` 隧道不稳，**Push 端到端联调先停**。需求与代码先收口提交；你后续用营销工具 / 过审后联调把环接上。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## 已定需求（权威）

| 文档 | 内容 |
|------|------|
| [google-mc-push-design](./2026-09-07-google-mc-push-design.md) | App 内 Generate → review → **Push to Google**（API 直写） |
| [google-mc-push](./2026-09-07-google-mc-push.md) | 实现任务拆解 |
| [landing-feed-checker-gmc-tools](./2026-09-06-landing-feed-checker-gmc-tools.md) | 营销站 Feed Checker + Google 拒审只读 |
| [cold-start-plg-playbook](./2026-09-06-cold-start-plg-playbook.md) | 冷启动优先级索引 |
| [google-mc-push-launch-checklist](./2026-09-07-google-mc-push-launch-checklist.md) | 过审后上线勾选 |

## 代码在哪

- Push：`phase0/adfeed/google_mc_push/` + App `GooglePushPanel`  
- 营销工具：`phase0/adfeed/public_tools/` + `landing-page/tools/`  
- 单测：`phase0/tests/test_google_mc_push_*.py`、`test_public_*`

## 你接着做工具闭环时建议顺序

1. **营销站工具** landing-only 上线（不碰审核 App）→ 获客  
2. Cloud 确认 App OAuth redirect；过审后 deploy Push  
3. 真店 Push 验收 → 再做拒审读回（原 read-loop 文档）

## 明确不做（仍有效）

编 GTIN、等 approved、文件型 data source 写入、V1 自动 delete、审核期改生产 Google listing。
