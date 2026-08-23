# Feed 主图选择器 — MVP Scope（锁定）

> **North Star:** `docs/plans/2026-08-12-mvp-north-star.md` — 支柱 ② 主图选择

> **图片 MVP = 检测 + 推荐 + 用户自选。** 不做 AI 去水印 / 白底 / OCR / 写回 Shopify。

**Goal:** 商家从 Shopify 商品已有图片里选 Feed 广告主图；系统推荐一张，用户可 per-SKU 更换并重生成 Feed（不烧 optimize 配额）。

**Architecture:** `feed_image_url` 存在 `product_variants`（Feed 侧 override，不写 Shopify）。生成时 `feed_image_url ?? variant.image_url ?? product.image_url`。候选图来自 Shopify 同步 + 按需 Admin API 拉全量 `images[]`。推荐用 `classify_image_risk` 域名启发式（零 API 成本）。

**Tech Stack:** Python store_db + FastAPI；React App Home（Shopify UI extensions）；pytest。

---

## 产品决策（锁定）

| 做 | 不做 |
|----|------|
| I03 WARN：可疑批发域名主图 | AI 去水印（万相）— **已从 App/API/生成链路移除** |
| 质量报告「主图建议更换」桶 | 批量粘贴 URL |
| 单 SKU 图片选择抽屉（网格缩略图） | 全店一键换图 |
| 推荐角标 + 用户点选 | OCR / 拼贴检测 / 白底 |
| Patch → DB → regen Feed（同 bulk_patch） | 写回 Shopify 主图 |
| 变体级 override（多色各用各图） | 参数表截图自动识别 |

**过审原则:** 图必须来自该商品 Shopify 图库；变体颜色与主图尽量一致；失败/脏图仅 WARN，不阻断 Feed。

---

## 数据模型

```sql
ALTER TABLE product_variants ADD COLUMN feed_image_url TEXT;
```

- `image_url` — Shopify 同步的变体/默认图（只读镜像）
- `feed_image_url` — 用户为 Feed 指定的图；NULL = 用 `image_url` 链

Shopify 再同步时 **保留** 已有 `feed_image_url`（save_variant merge）。

---

## API

### `GET /api/app/feed-images?sku={sku}`

```json
{
  "sku": "SKU-001",
  "product_id": "...",
  "shopify_product_id": "...",
  "current_feed_image": "https://cdn.shopify.com/...",
  "effective_image": "https://...",
  "recommended_url": "https://cdn.shopify.com/...",
  "candidates": [
    {"url": "...", "risky": false, "reason": "", "tags": ["variant_default"]},
    {"url": "...", "risky": true, "reason": "domain:alicdn.com", "tags": ["product"]}
  ]
}
```

### `POST /api/app/quality/image_patch`

Body 同 bulk_patch 风格：

```json
{
  "patches": [{"sku": "SKU-001", "image_url": "https://cdn.shopify.com/..."}],
  "platforms": ["google"],
  "languages": ["US"],
  "regenerate": true
}
```

---

## 推荐逻辑（MVP）

1. 变体在 Shopify 绑定的图（`variant.image_url`）且非 risky → 推荐  
2. 否则候选列表中第一张 `cdn.shopify.com` 且非 risky  
3. 否则第一张非 risky  
4. 若全非 risky → 变体默认或 featured；全部 risky → 仍返回列表，UI 标「不建议投放」

---

## UI（HomePage）

1. 生成后 `quality_report.warnings` 中 `rule_id=I03` → **主图建议更换** 桶  
2. 每行 SKU + 当前缩略图 + **换主图** 按钮  
3. 抽屉：候选网格、推荐 ★、risky ⚠、选中高亮  
4. **使用选中图并重生成 Feed** → `image_patch`（不消耗 optimize 配额）  
5. 移除原「去除图片水印」checkbox

---

## 文件清单

| 文件 | 变更 |
|------|------|
| `adfeed/feed_image.py` | 新建：候选聚合、推荐、patch 编排 |
| `adfeed/store_db.py` | `feed_image_url` 迁移 + patch helper |
| `adfeed/feed_quality.py` | `diagnose_row_basics` 增加 I03 |
| `adfeed/pipeline.py` | 读 `feed_image_url`；删除 clean_images 块 |
| `adfeed/api.py` | 新 endpoints；删 remove_watermarks/clean_images |
| `adfeed/quality_bulk.py` 或 `feed_image.py` | `image_patch_and_regen` |
| `tests/test_feed_image.py` | 推荐 + patch |
| `HomePage.jsx` | 图片桶 + 抽屉 |
| `products.ts` | `fetchFeedImages` / `patchFeedImage`；删 watermark 参数 |

**保留但不接入产品链路:** `image_processor.py`（仅 `classify_image_risk` 被 feed_image 引用；万相函数暂留代码库，无 UI/API 入口）。

---

## 测试

```bash
cd phase0 && .venv/bin/python -m pytest tests/test_feed_image.py tests/test_store_compliance.py -q
```

---

## Out of scope（后续）

- 「一键应用推荐」轻批量  
- 商品级（非变体）统一主图  
- 从 quality 报告 deep-link 到 Shopify Admin 换图  
- S7b OCR / S7c 白底
