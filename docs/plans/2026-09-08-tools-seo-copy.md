# 两工具 SEO + Landing 宣传改动清单（2026-09-08）

**范围：** 仅 `landing-page/`（landing-only 可发）。**不动** Shopify 嵌入式 App / 审核包。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 1. 改了哪些文件

| 文件 | 改动 |
|------|------|
| `landing-page/tools/feed-checker.html` | title / description / keywords / canonical / Open Graph / Twitter；强化 H1 下方 lead 文案 |
| `landing-page/tools/google-issues.html` | 同上；H1 改为带关键词的 Disapproval Checker |
| `landing-page/tools/index.html` | 工具目录页 SEO + 卡片文案对齐两个产品名 |
| `landing-page/index.html` | How 区增加 Free tools 双链；页脚加 Free tools |
| `landing-page/styles.css` | `.how-tools*` 样式 |

---

## 2. SEO 是什么（本轮做了什么）

SEO = 让搜索引擎和用户看懂「这页解决什么问题」，更容易搜到并点进来。

本轮 **页面级 SEO 基建**（不是买广告、不是刷外链）：

1. **Title** — 浏览器标签 + 搜索结果标题  
2. **Meta description** — 搜索结果摘要  
3. **Canonical** — 告诉 Google 正式网址，避免重复页  
4. **Open Graph / Twitter** — 分享到社交时的标题摘要  
5. **H1 + 首段** — 正文里自然出现主关键词  
6. **内链** — 首页 How 区、页脚链到工具（权重互相导）

**还没做（以后可加）：** 独立博客长文、sitemap 提交、外链外联、Search Console 验证（若未做）。

---

## 3. 各页 SEO 文案（可直接对照线上）

### 3.1 Feed Checker — `https://deltfu.com/tools/feed-checker`

| 字段 | 内容 |
|------|------|
| **Title** | Free Google Shopping Feed Checker — Validate XML Before Ads \| AdFeed |
| **Meta description** | Free Google Shopping feed checker: paste a feed URL or upload XML. Spot noisy titles, missing brand, color/size gaps, and identifier issues—never fake GTINs. No Shopify install. |
| **Keywords（辅助）** | Google Shopping feed checker, product feed validator, Google Merchant feed errors, missing brand GTIN, shopping feed XML |
| **Canonical** | `https://deltfu.com/tools/feed-checker` |
| **H1** | Google Shopping Feed Checker |
| **主意图词** | Google Shopping feed checker / product feed validator / feed XML errors |
| **Waitlist source** | `feed-checker` |

### 3.2 Disapproval Checker — `https://deltfu.com/tools/google-issues`

| 字段 | 内容 |
|------|------|
| **Title** | Google Merchant Center Disapproval Checker — Account or Feed? \| AdFeed |
| **Meta description** | Free Google Merchant Center disapproval checker. Connect read-only, see if Shopping issues look account-level or product-feed related—and what to fix next. No product changes. |
| **Keywords（辅助）** | Merchant Center disapproval, Google Shopping disapproved, product disapproved Merchant Center, account suspension vs feed, GMC issues |
| **Canonical** | `https://deltfu.com/tools/google-issues` |
| **H1** | Google Merchant Center Disapproval Checker |
| **主意图词** | Merchant Center disapproval / Google Shopping disapproved / account vs feed |
| **Waitlist source** | `google-issues` |

### 3.3 Tools index — `https://deltfu.com/tools/`

| 字段 | 内容 |
|------|------|
| **Title** | Free Google Shopping Tools — Feed Checker & Disapproval Diagnostic \| AdFeed |
| **Meta description** | Free Google Shopping tools: validate your product feed XML, or diagnose Merchant Center disapprovals (account vs feed). No Shopify install. Then join the AdFeed waitlist. |
| **Canonical** | `https://deltfu.com/tools/` |
| **H1** | Free Google Shopping tools |

### 3.4 首页 How 区宣传（非独立 SEO 页）

- 文案：**Already have a feed or Merchant Center account?**  
- 链：Feed Checker → `/tools/feed-checker`；Disapproval Checker → `/tools/google-issues`  
- 页脚增加 **Free tools** → `/tools/`

---

## 4. 建议你怎么用这些 SEO

1. 发 landing-only 后，用无痕打开上述 URL，看标签标题是否更新。  
2. （可选）Google Search Console 添加 `deltfu.com`，提交 `https://deltfu.com/tools/`、两工具页。  
3. 外联/Reddit 贴工具链接时用完整 URL + 简短问题句（与 H1 同义即可）。  
4. 看 waitlist 后台 `source=feed-checker` / `google-issues` 是否增长。

---

## 5. 部署方式（审核安全）

```bash
bash phase0/scripts/prod/deploy-landing-only.sh
```

只同步营销静态页 + 公共 API 文件；**不** rebuild / restart `adfeed-web`（审核中的 App Home）。
