# Design Diff — 标题维持当前 + 变体属性补齐（截图层）

**日期：** 2026-08-11  
**状态：** **PARTIAL / 半过期** — 变体属性合同仍有效；**标题出口叠层与 eprolo 前缀以字段合同为准作废**  
**纠偏：** 见 `2026-08-14-feed-field-contract.md`、`2026-08-14-design-audit-cleanup.md`  
**仍成立：** 标题脑与属性脑分离；真 `?variant=`；color/size/system/type 由变体清洗产出  
**已废 / 勿再实现：** 靠 `title_guard.polish` 多层对齐当标题主人；Brand 静默 eprolo「保持」；为对齐在出口再插花色/Size  
**前提决策：** 标题继续用现行 `title_optimizer` 出 **骨架**；渲染最多拼本行 color+size；属性层吸收「按变体 JSON 清洗」。  
**关联：**
- `2026-08-10-high-quality-feed-engine-design.md`（过审引擎总设计）
- `phase0/adfeed/title_optimizer.py`（现行标题 Prompt）
- 实盘：`variant=` 真 Shopify ID（已落地）；`size_system` / `size_type` 由变体清洗补

---

## 0. Diff 一句话

| 层 | 现状 | Diff 后 |
|----|------|---------|
| **标题** | 现行引擎（场景长尾 + 多语 + 描述金字塔） | **保持**；仅微调场景优先级（可选） |
| **变体属性** | 色/码分散在 normalizer / feed_quality | **新增**「变体属性合同」：每变体产出 color/size/system/type + **真 Shopify variant id** |
| **链接** | 常写入内部 hex SKU | **强制** `?variant={shopify_variant_id}` |

---

## 1. 目标 / 非目标

### 1.1 目标

1. **标题质量不降**：不换成截图的 `[品名]+[受众]+[卖点]` 通吃公式。  
2. **属性 cover 补齐**：每个 Feed 行具备干净的 `g:color` / `g:size` / `g:size_system` / `g:size_type`，与标题可对齐。  
3. **链接可定位变体**：`g:link` 使用 Shopify Admin 数字 `variant_id`。  
4. **可解释**：优化日志能区分「标题 AI」vs「变体属性清洗」。

### 1.2 非目标

- 不重写 DE/FR/ES/IT 标题模板。  
- 不把 color/size 强行塞进标题 Prompt 的同一轮 JSON（避免抢上下文、拖慢标题）。  
- 不改价币种 / 敏感词 / 图片主设计（沿用已定稿）。  
- 本文件不写实现计划、不改代码。

---

## 2. 架构 Diff（数据流）

### 2.1 现状（简化）

```
Shopify product
  → title_optimizer（产品级标题/描述/tags）
  → 展开变体行（色码常来自 option 原文）
  → feed_quality enrich（空色 Multicolor / 空码 One Size …）
  → link 用内部 sku/hex
  → Feed XML
```

### 2.2 Diff 后

```
Shopify product + variants[]（含 shopify_variant_id, option1/2/3）
        │
        ├─► [A] Title path（不变主干）
        │     title_optimizer → platform rewrite → 产品级「广告标题骨架」
        │
        └─► [B] Variant attribute path（新增，吸收截图层）
              VariantAttributeCleaner
                输入: 每个变体的 options + 标题/描述上下文
                输出: {
                  shopify_variant_id,   // 数字字符串，必填
                  g_color,
                  g_size,
                  g_size_system,        // 服饰/鞋: US；其它: 省略或空
                  g_size_type,          // 服饰/鞋: Regular（可配置）；其它: 省略
                  source: variant|dict|llm|fallback
                }
        │
        ▼
Merge 成 Feed 行:
  title = 骨架标题 + title_guard 轻量对齐色/码（已有）
  color/size/system/type = [B]
  link = ...?variant={shopify_variant_id}&currency=...
        │
        ▼
feed_quality（兜底仍保留）→ sensitive → Feed
```

**原则：** 标题脑与属性脑分离；合并时字段为准，标题不得与字段矛盾。

---

## 3. 标题层 Diff（维持当前，仅可选微调）

### 3.1 保持不变

- 角色：Google Shopping title optimizer（多语模板）。  
- 服装公式：`[Gender] + [Core Category] + [Key Feature/Material] + [1-2 Usage Scenes]`。  
- 黄金前 30 字含品类名词；`front_70` 硬顶；禁 One Size / Free Shipping 等进标题。  
- 输出：`front_70` / `rest` / `ai_tags` / `description_snippet`。  
- 后置：`title_guard.polish_feed_title`。

### 3.2 已拍板微调：场景「有则加」

| 项 | 现状 | **已定** |
|----|------|----------|
| 场景优先级 | Prompt 写 Scene = #1，挤不下先丢色/材质 | **品类 > 核心功能 > 色/材质 > 场景（有则加）**；塞不下**先丢场景** |
| Brand 前缀 | 管线侧可能加 eprolo | 保持 |

**明确不做：** 换成截图的 `[Core Product Name]+[Audience]+[Key Features]` 作为主公式。

---

## 4. 变体属性层 Diff（截图能力产品化）

### 4.1 模块名（设计级）

`VariantAttributeCleaner`（实现时可落在 `variant_attributes.py` 或扩展现有 normalizer —— 实现计划再定）。

### 4.2 输入合同（每个变体）

```text
{
  shopify_product_id,
  shopify_variant_id,          // 必须从 Shopify API 带来；缺失则本变体 WARN/FATAL 策略见下
  options: [{name, value}, ...], // 如 Color/颜色, Size/尺码
  product_title,
  product_description_html_or_text,
  gpc_path / is_apparel_like
}
```

### 4.3 输出合同（每个变体）

```text
{
  "shopify_variant_id": "12345678901234",   // 仅数字 ID
  "g_color": "Black",                       // 标准英文色；禁止「现货」「升级款」等
  "g_size": "M" | "One Size" | ...,
  "g_size_system": "US" | "",               // 服饰/鞋服/配饰（需尺码者）→ US；否则 ""
  "g_size_type": "Regular" | "",            // 同上默认 Regular；大码策略可后置
  "source": {
    "color": "variant|dict|llm|fallback",
    "size": "variant|dict|llm|fallback"
  }
}
```

### 4.4 清洗规则（从截图吸收 + 与总册对齐）

| 步骤 | 规则 |
|------|------|
| 去噪 | 变体 option 去掉：现货、升级款、新款、爆款、包邮、以及纯营销前缀 |
| 色 | option 映射 → 词典（中英）→（可选）LLM 读标题+描述 → 仍空则 **`Multicolor`**（**不用 Default**） |
| 码 | option 映射 → S/M/L/数字码标准化 → 服饰类仍空则 **`One Size`**（OSFA/均码归一） |
| size_system | `is_apparel_like` 或鞋类 → `US`；否则不输出或空 |
| size_type | 同上 → 默认 `Regular`；若 option 含 Plus/Petite 等可映射（P1） |
| 禁止 | 伪造 GTIN；用 myshopify 域名当 brand（brand 仍走现有策略） |

### 4.5 与现行 `feed_quality` 关系

- Cleaner **先**跑；`feed_quality` **后**跑作安全网（仍保留 One Size / Multicolor / condition 等）。  
- 若 Cleaner 已写入真色，**禁止**再被 Multicolor 覆盖。  
- 日志：`VA01` 色清洗、`VA02` 码清洗、`VA03` 补 size_system/type、`VA04` 缺失 shopify_variant_id。

### 4.6 LLM 是否用于属性层

| 期 | 策略 |
|----|------|
| **P0** | 规则 + 词典为主（快、稳、便宜）；无色再走现有 `color_extract` |
| **P1** | 可选「整品一次 LLM 返回变体数组」（接近截图 JSON），需强校验 shopify_variant_id 必须来自输入白名单，禁止模型编造 ID |

---

## 5. 链接 / ID Diff

### 5.1 问题（实盘已证实）

`g:link` 中 `variant=A8842A68…` 为内部 hex，**0/147** 为 Shopify 数字 ID。

### 5.2 目标行为（已拍板）

```text
https://{shop}/products/{handle}?variant={shopify_variant_id}&currency={ISO}
```

- `shopify_variant_id`：Shopify REST/GraphQL 数字 ID（库里已有则必须用）。  
- **有真 ID → 必须写入 `?variant=`。禁止用内部 SKU/hex 冒充**（避免广告点到错款、用户白花钱）。  
- **无真 ID → 也不写假 ID**：  
  1. 该行进报告 **黄灯 VA04**（可升红若产品策略要「禁止投放」）。  
  2. **生成结果页必须明确提示用户**：例如「N 个变体缺少 Shopify Variant ID，链接无法定位到具体色/码；请重新同步商品后再生成，在修好前不建议投放这些 SKU」。  
  3. 链接可暂时只有商品页 + `currency=`（不带错误 variant），但 UI 不得显示为「绿通可投」。  
- 行业对齐：Google 要求 link 落到**广告展示的那一款**；DataFeedWatch 等强调用 `variant_url` / 真 variant，而不是父商品默认页。顶级工具不会用自造 ID 冒充 Shopify variant。

---

## 6. Feed 字段映射 Diff

| Feed 字段 | 来源（Diff 后） |
|-----------|-----------------|
| `g:title` | 标题引擎 + guard |
| `g:description` | 现有描述策略 |
| `g:color` | VariantAttributeCleaner |
| `g:size` | VariantAttributeCleaner |
| `g:size_system` | Cleaner（服饰等） |
| `g:size_type` | Cleaner（服饰等） |
| `g:gender` / `age_group` / `condition` | 现有 autofix（不变） |
| `g:identifier_exists` / brand | 现有无码策略（不变） |
| `g:link` | handle + **真 variant id** + currency |
| `g:id` | 保持现有 SKU/稳定 id 策略（可与 variant id 不同；但 link 必须用 Shopify variant id） |

---

## 7. UX / 报告 Diff（最小）

在现有 `quality_report` 上增加可读分组（不必新页面）：

```text
标题优化：…（title_compare 已有）
变体属性：
  - 已清洗色 N / 码 N
  - 已补 size_system=US N
  - 缺 Shopify variant id N（黄）
```

高亮微调表：增加 `size_system` / `size_type` / `variant_id` 列（只读亦可）。

---

## 8. 验收标准（本 Diff）

1. 标题样例仍呈现现行风格（品类靠前 + 可有场景），**不是**截图短公式主导。  
2. 服饰行：`color`/`size` 非空；`size_system=US`；`size_type=Regular`（或文档允许的映射值）。  
3. 空色兜底为 **Multicolor**，不为 Default。  
4. 空码服饰为 **One Size**。  
5. Feed 中 `variant=` **≥99%** 为纯数字 Shopify ID（允许个别缺 ID 黄灯）。  
6. 标题与 `g:color` 不系统性矛盾（guard 对齐）。  
7. 回归：价币种门、无码、敏感词、三色灯行为不被破坏。

---

## 9. 明确的「不做清单」

- ❌ 替换 `_PROMPT_EN` 为主的截图 Role/公式  
- ❌ 颜色万能值改用 Default  
- ❌ 标题里强制写 One Size  
- ❌ 模型生成假 variant id  
- ❌ 本 diff 范围内做安检舱动画 / 动态 URL 主次调整

---

## 10. 建议落地顺序

1. ~~同步 + 真 `shopify_variant_id` 写入 link~~ → **已完成**（2026-08-11）  
2. 标题 Prompt：场景改为「有则加」（已拍板）  
3. VariantAttributeCleaner P0（规则/词典 + size_system/type + Multicolor 保持）  
4. 与 feed_quality 去重、报告字段  
5. （可选）P1 整品变体数组 LLM

---

## 11. 决策状态（全部拍板）

| 项 | 状态 |
|----|------|
| 标题维持当前引擎 | **已定** |
| 场景优先级 | **已定：有则加**（挤不下先丢场景，更可控） |
| 颜色空 | **已定：保持 Multicolor**（不用 Default） |
| Variant ID | **已定且已修**：有真的必须用；禁止假 ID；缺失黄灯 + UI 提示 |

下一步：实现计划见 `2026-08-11-variant-attrs-scene-priority.md`。
