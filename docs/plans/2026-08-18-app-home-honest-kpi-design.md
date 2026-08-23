# 2026-08-18 App Home KPI 真实值（一眼看懂）

Field contract: docs/plans/2026-08-14-feed-field-contract.md  
North Star: docs/plans/2026-08-12-mvp-north-star.md

## Goal

KPI 只显示可核对的真值；刷新后「要处理」仍来自上次生成的 `quality_report`；不做 mock、不做虚高分母。

## UI

1. **要处理** — 通栏主卡 + badge；SKU 待办 ∪ 店铺门禁  
2. **本市场可投** — 次卡；`max(单 Feed item_count) − 要处理 SKU`；无数则显示 —  
3. **Feed 文件** — 次卡；库里有效 Feed 条数（无 `/ 勾选槽位`）

一句 disclaimer：来自上次生成，不是 Google 已过审。

## Data

`GET /api/app/feeds` 附带最近一次 `completed` job 的 `quality_report` + `last_job`。

## Non-goals

不接 GMC Content API；不编 Readiness %；不改 Feed 字段主人。
