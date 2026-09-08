# 两工具 SEO + Guides 第一批（2026-09-08）

**范围：** 仅营销站 `landing-page/` + nginx（landing-only）。**不动** Shopify 嵌入式 App / 审核包。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

## 架构

- **Homepage** = 品牌 + 转化（实体：Clean Google Shopping feed / 1688→Shopify→Google）
- **Tools** = 搜索入口（免登录）
- **Guides** = 问题型 SEO → 链回 Tools → waitlist

```
Google Search
   ├─ "feed checker"     → /tools/feed-checker
   └─ "product disapproved" → /tools/google-issues
Guides 也链到上面两个工具 → AdFeed waitlist
```

## Tools SEO（已对齐分析文案）

### `/tools/feed-checker`

| 字段 | 内容 |
|------|------|
| Title | Google Shopping Feed Checker — Free Feed Validator \| AdFeed |
| H1 | Check Your Google Shopping Feed |
| Lead | Find missing attributes, invalid values, and product data issues before Google Merchant Center does. |
| Target | Google Shopping Feed Checker |

### `/tools/google-issues`

| 字段 | 内容 |
|------|------|
| Title | Google Shopping Disapproved? Diagnose Your Merchant Center Issues \| AdFeed |
| H1 | Google Shopping Disapproved? |
| Target | Google Shopping disapproved / Merchant Center issues |

## Guides（第一批）

| URL | 用途 |
|-----|------|
| https://deltfu.com/guides/ | 目录 |
| https://deltfu.com/guides/google-shopping-disapproved | 拒审含义 / account vs feed |
| https://deltfu.com/guides/google-shopping-feed-errors | Feed 常见错误 → Feed Checker |

## Homepage

- Eyebrow: Clean your Google Shopping feed  
- H1: From 1688 → Shopify → Google Shopping  
- 一句实体：clean product data + stable feed, no inventing identifiers  

## 改动文件

`tools/*.html`, `index.html`, `guides/*`, `styles.css`, `dev_server.py`, `nginx/deltfu.com.conf`

## 下一批（未做）

更多 guides 变体、1688 niche 页、Search Console / sitemap。

部署：`bash phase0/scripts/prod/deploy-landing-only.sh`
