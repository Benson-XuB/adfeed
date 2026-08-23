# AdFeed — Feed 字段合同（禁止出口打补丁）

**日期：** 2026-08-14  
**状态：** **LOCKED** — 写 Feed / 改标题 / 改属性 / 跟审查清单时必须先对照本文  
**服从：** `2026-08-12-mvp-north-star.md`（北星仍是过审闭环；本文约束 **怎么改 Feed 内容**）  
**为何锁定：** 2026-08-14 用外部 AI 审查清单在出口叠层（钉 Size、把花色/Style 塞进 color），数字变好、购物标题变差。根因是 **字段没有唯一主人 + 用补丁当产品**。

---

## 0. 每次动手前的大前提（复制到计划/PR 开头）

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

1. **购物卡优先于审查打分表。** 一条标题要像人会搜、会点的衣服，不像 1688 属性墙。  
2. **每个字段只有一个主人。** 发现问题改主人那一层；禁止在 `feed_generator` / `title_guard` 出口再叠一层「补上」。  
3. **变体唯一用组合键，不污染 color。** `(item_group_id, color, size, pattern)` 唯一即可。  
4. **不造 GTIN / 假 MPN / 假 COGS。** 店里缺的：能从变体算的自动写对；不能编的在 App 里让商家确认（尤其广告品牌）。  
5. **回归看三件真商品的购物标题，不看「重复标题少了多少」。**

---

## 1. 字段主人（合同）

| 字段 | 主人 | 允许长什么样 | 禁止 |
|------|------|----------------|------|
| **title** | **一个**作者：标题模型产出「商品骨架」；渲染时拼接 **本行会搜 pattern（若有）+ color + size 各一次**（变体区分，与 Google「变体细节进标题」一致） | 短、可读；前 30 字有品类；花色变体标题能分清 | 出口再插 Plus Size/材质墙；`Style 1` 进标题；同时保留 `S-5XL` 又钉 `Size L`；为审查计数硬塞词 |
| **color** | `resolve_gmc_color` / 变体清洗 | GMC 色名：`Black`、`Navy Blue`、`Black/White` | `Brown Style 1`、`White Curved Stripes` 当 color；为 uniqueness 把 option 原文倒进 color |
| **pattern**（或 custom_label_0） | 变体 option 里非色差（Floral、Stripe…） | 短词：`Floral`、`Stripe`、`Polka Dot` | 把这些写进 color；`Style 1` 当花色进标题；用 Style 代号堆词过审 |
| **item_group_id** | Shopify 产品 id；若存在不透明款式轴（Style/Design/Type/款式…）则 `{productId}-{axisKey}` | 同一款式轴内色码变体共享 | 把两件不同衣服硬捏同一 group 仅靠假 pattern 去重 |
| **size** | `normalize_size` | 本行一个码：`L`、`2XL`、`One Size` | `"L" in "XXXL"` 式包含匹配；`4XL` 与 `5XL` 收成同一个值 |
| **brand** | 店铺 `default_brand` → 可读店名；App **确认** | 消费者认知的店品牌 | 静默供应商名 `eprolo` 当全站默认；为「自洽」删掉 brand 装无主商品 |
| **identifier_exists** | 无码通道策略 | 无 GTIN：**no** + 店品牌；有真条码则写 GTIN、不要假 MPN | 用内部哈希冒充 mpn；要求商家必须有 GTIN 才能出 Feed |
| **description** | 描述格式化 / 一句卖点 | 人话 + 精简规格 | 整页尺码表当唯一描述；出口再拼一段属性清单 |
| **shipping** | XML 模板 | XML 用嵌套 `<g:shipping>`；CSV 才用 `US::service:price` | 为 CSV 审查去改 XML shipping |

**已修且属于「主人层 bug」、不是补丁、应保留：** `Colorful`→`Multicolor`；删除假 MPN；字母尺码最长匹配（XXXL 不是 L）。

---

## 2. 反模式（看到就停）

| 反模式 | 例子 | 应做 |
|--------|------|------|
| 出口再加一层 | `pin_variant_size`、enhance 后再插 cue | 回到标题主人：模型不要写尺码范围；渲染只加本行码 |
| 用脏字段换 uniqueness | color=`Brown Style 1` | color=`Brown`，pattern=`Style 1` |
| 跟着外部审查打点 | 为 COGS/纯色/删 brand 改一整版 | 对照本文第 1 节：能自动的自动，不能编的走 UI |
| 多层标题后处理共存 | 清洗 + 插花色 + 品牌 + 材质 + Size + Plus | **减层**：最多「骨架 + 本行色码」 |
| 店里没有就不管 / 店里没有就编 | 无品牌就 eprolo；无成本就填假 COGS | 品牌：店名预填 + UI 确认；COGS：选填，空着也能出 Feed |

---

## 3. 缺数据时怎么对用户负责

| 缺口 | 引擎 | UI |
|------|------|-----|
| 本行有色/码，标题没写上 | 渲染时带上 **一次**，不要再叠范围尺码 | 不必让商家手填 |
| 无 GTIN | `identifier_exists=no`，不造码 | 说明已走无码通道；有 UPC 去 Shopify 填 |
| 无店品牌 | 可读店名预填，**不要**默默用供应商默认 | 「广告品牌」确认；黄灯：别用货源厂名 |
| 无 COGS | **不写**该列 | 可选：要利润报表再填；不挡生成 |
| Style 1/2 同色 | color 相同 + pattern 区分 | 列表可展示「同色不同款」 |

---

## 4. 改代码时的作业方式（硬门禁）

1. 计划/PR 开头贴第 0 节两行路径。  
2. **动手前在回复里写清：** 改哪个字段主人？修主人还是出口叠层？验收是购物标题还是审查分数？  
3. 出口叠层 / 审查分数验收 / 编假值 → **默认拒绝，先停手问产品。**  
4. 外部 AI / GMC 诊断是输入，**不是**需求清单；与本文冲突时以本文为准。  
5. 验收：同一条牛仔裤、裙子、夹克，改前/改后标题是否 **更短、更好懂**。禁止只用「重复标题计数」当成功。  
6. **已知债只许拆不许加厚：** `pin_variant_size`、`_with_pattern_qualifier` 脏 color、静默 `eprolo` —— 下一程是减层/分家/UI 确认，不是再包一层。

Cursor 每次会话会带 `.cursor/rules/feed-field-contract.mdc`；与本文冲突时以本文 + 北星为准。

---

## 5. 下一步实现（减层，不是加层）

1. 标题：骨架 + 渲染本行 **会搜 pattern（可选）+ color + size** 各一次。  
2. 花色从 color 拆到 pattern；`Style N` 不进 pattern/标题。  
3. App：广告品牌确认，去掉静默 eprolo。  
4. 描述：一句卖点，尺码表缩短或降级。

**已落地：** 会搜 pattern 与色码同级渲染（全品类，不限裙子）。