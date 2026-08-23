# Feed Link Query Allowlist — Deferred

**日期：** 2026-08-11  
**状态：** ⏸ 后置 / 不做（已记入 backlog）  
**触发再开：** 支持「粘贴任意脏 URL 导入」、或实测大量 Feed 链接带插件垃圾参、或客户明确要求 `canonical_link` / 可控 UTM

---

## 原提议（未实施）

`build_product_link` 改为严格白名单：Feed `link` 只保留 `variant` + `currency`，其余 query 一律剥掉。

---

## 为何先不做

1. **App 主路径已从** `{site}/products/{handle}` **重建链接**，多数情况下本身无垃圾参；不清洗对当前投放几乎无影响。
2. **行业主流（GoDataFeed / DataFeedWatch / Google 官方）优先的是真变体直达**（`?variant=`），不是默认剥光 query；UTM 多为可选追加规则。
3. 严格白名单有产品副作用：会挡掉「Feed 自带联盟/营销参」等玩法；收益与风险不对称。
4. **变体 ID 强制拼接 + VA04** 已落地，覆盖「点蓝 M 进红 S」主伤。

---

## 已做（本项不重复）

- [x] `resolve_shopify_variant_id`：仅数字 Shopify ID，拒假 hex SKU  
- [x] pipeline 拼 `?variant=` + `?currency=`  
- [x] 缺 ID → VA04 黄灯  

## 明确不做（直到再开）

- [ ] `build_product_link` query 白名单清洗  
- [ ] LINK01 质量事件  
- [ ] Feed 预埋 UTM 规则引擎  
- [ ] `canonical_link` 字段  

---

## 若再开时的建议方向

优先 **「源头用 handle 重建」**（保持现状）+ 仅在导入脏链路径加白名单；不要一上来全局剥光。可选增强：商家可控追加 UTM、或 Google 建议的 `canonical_link`。
