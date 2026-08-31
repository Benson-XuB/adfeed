# Google Ads 只读指标 — Phase 2 收口（P2-A）

**日期：** 2026-09-01  
**状态：** ACCEPTED（7+30 可切换；**禁止任何生产 deploy**）  
**分支：** `feature/google-mc-issues`  

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
Parent: docs/plans/2026-08-30-google-mc-ads-read-loop-design.md §Phase 2
```

## 范围

- 增量 OAuth `adwords`（已有）
- 手动同步 `shopping_performance_view`，窗口 **7 / 30 可切换**
- 汇总卡（展示/点击/花费/转化）+ 商品行；无商品级则降级系列并标注
- 持久化所选 `ads_customer_id` + `window_days`
- 链到「过审问题」
- **只读**；绝不 mutate Ads

## 硬禁止

- `shopify app deploy` / 改审核中生产 App / listing / 隐私 / 生产 toml
- 自动投放、建系列、改出价

## 验收

- [ ] mock sync 7 与 30 分窗落库、互不覆盖
- [ ] UI 可切换窗口并重新同步
- [ ] 汇总数字 = 当前窗口 rows 合计
- [ ] 无 deploy 动作
