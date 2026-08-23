# AdFeed AI — iframe App Home（React Router 官方模板）设计

**日期：** 2026-08-20  
**状态：** Approved（方案 2）  
**Field contract:** `docs/plans/2026-08-14-feed-field-contract.md`  
**North Star:** `docs/plans/2026-08-12-mvp-north-star.md`  
**背景：** 现有 `admin.app.home.render` UI 扩展适合 Custom / 本地测；公开 App Store 要求 **iframe 嵌入式 App Home**。本设计不推倒 Feed 引擎，只换商家主界面宿主。

---

## 1. 目标 / 非目标

### 目标

- 公开上架可用的 **嵌入式 iframe App Home**（Shopify 官方 **React Router** 模板）。
- 商家路径与现网一致：确认广告品牌 → 选平台/国家 → 选商品 → 生成 → 复制 Feed 链接 → 升级套餐。
- **未来可扩展**：多页路由（Home / Plans / Settings）、NavMenu、后续加账单历史等，不靠再叠一层薄壳。
- 继续走现有 FastAPI：`/api/app/*`、Billing、GDPR、字段合同不变。

### 非目标（本轮不做）

- 部署 / 绑定 `deltfu.com`（用户明确先本地）。
- 改 title / color / size 生成逻辑、假 GTIN、静默 eprolo。
- Built for Shopify 性能徽章。
- 把整个后端改写成 Node（**禁止**；Feed 仍在 Python）。

---

## 2. 为什么不是「之前做错了」

| 层 | 现状 | 公开上架 |
|----|------|----------|
| Feed / 配额 / GDPR / Billing API | 正确，保留 | 保留 |
| App Home UI 扩展 | Custom / 本地正确 | **不能当公开主入口** |
| iframe + 官方模板 | 未建 | **要建** |

扩展版不是废品：产品交互与文案是迁移源；换的是 **谁托管首页**。

---

## 3. 架构

```
Shopify Admin (iframe)
    │  App Bridge + session token（模板 authenticate.admin）
    ▼
phase0/add-feed-ai/web  （React Router 嵌入前端）
    │  Authorization: Bearer <session JWT>
    │  BACKEND_URL = tunnel | 以后 deltfu
    ▼
phase0/adfeed FastAPI
    │  require_store / shopify_billing / pipeline …
    ▼
SQLite store_db + feeds/
```

- **鉴权：** 浏览器侧用 App Bridge `idToken` / 模板提供的 session，调用 FastAPI 时带 `Authorization: Bearer`，与现扩展相同（`shopify_auth.require_store`）。
- **商品列表：** 优先继续用 Admin GraphQL Direct API（模板里也可 `authenticate.admin` + Admin API）；生成与配额仍打 FastAPI。
- **application_url：** 指向 **web 应用根**（本地隧道转发到 React Router 端口，或 CLI `shopify app dev` 托管）；不再指望扩展独占首页。

---

## 4. 仓库布局

```
phase0/add-feed-ai/
  shopify.app.toml          # application_url → web；保留 scopes / webhooks
  web/                      # NEW：React Router 官方模板落地处
    app/routes/app._index   # 商家主流程（从 HomePage 迁）
    app/routes/app.plans    # 套餐对比页
    app/shopify.server.ts   # 模板鉴权
  extensions/
    app-home/               # 过渡期保留对照；公开提交前禁用或删除主入口依赖
    app-tools/              # Sidekick 可保留（describe_adfeed）
  shared/                   # 可抽 API client；或 web 内新建 app/lib/adfeed-api.ts
phase0/adfeed/              # 不变（除必要时 CORS 允许 web origin）
```

**并存策略（迁移期）：**

1. Phase A：web 可装可开，主流程可用。  
2. Phase B：toml / Partner 以 web 为 App URL；扩展 `admin.app.home.render` 从发布版本移除或留空。  
3. 本地可用 feature 开关临时打开旧扩展对照，**不**作为审查版本主路径。

---

## 5. UI 迁移范围

| 页面 / 能力 | 来源 | 目标 |
|-------------|------|------|
| 主流程 Home | `extensions/app-home/.../HomePage.jsx` | `web/app/routes/app._index.tsx` |
| 套餐对比 | HomePage `view=plans` | `web/app/routes/app.plans.tsx` |
| i18n | `i18n-messages.js` + locales | 迁到 web（可先中英对象，后接 `shopify.i18n`） |
| Polaris | `s-*` web components | **Polaris React**（官方模板默认）— 允许视觉一致但组件 API 重写 |
| API | `shared/models/products.ts` | `web/app/lib/adfeed-api.ts`（复制并适配，不硬依赖扩展 runtime） |

**组件原则：** 不在 iframe 里继续依赖 `document.body` + Preact `render` 扩展入口；用 React 路由 + Polaris React。

---

## 6. 本地开发（本轮）

1. FastAPI `:8000` + Cloudflare tunnel（或 `shopify app dev` 代理）。  
2. `shopify app dev` 同时起 web；`application_url` / `auth.redirect_urls` / webhooks 指向当前可达 HTTPS。  
3. `ADFEED_BILLING_TEST=true` 本地测扣费；假开通可在后续加固任务加，不挡 iframe 骨架。  
4. **Basic 店**若不能 `app dev`：继续 `shopify app deploy` 发含 web 的版本（与现扩展部署方式同类）。

生产 `deltfu.com`：本设计预留 `BACKEND_URL` / `SHOPIFY_*`，**实现与验收不依赖** 本机 SSH 通服务器。

---

## 7. 风险与缓解

| 风险 | 缓解 |
|------|------|
| HomePage 很大，一次迁不完 | 分里程碑：骨架可登录 → 生成 Feed → 套餐 → 色码/图修补 |
| Polaris 组件差异 | 按功能迁，不追求像素级复制扩展版 |
| 双入口混淆审查 | 提交公开版前只保留 iframe；文档写明 |
| CORS | FastAPI 已有 shopifycdn / admin 正则；补 web 隧道 origin |

---

## 8. 验收（本地）

1. 开发店打开 App → **iframe** 加载 web，不是「Backend is running」占位页，也不是仅扩展 runtime。  
2. 确认品牌 → 选 Google+美国 → 生成 → 出现 Feed 链接可复制。  
3. 打开 Plans 页 → 可点 Starter（本地 test charge 或明确错误，不崩）。  
4. Network：API 打隧道/本机后端，带 Bearer。  
5. 字段合同：不新增假 GTIN / 出口叠层。

---

## 9. 下一步

实现计划见：`docs/plans/2026-08-20-iframe-app-home-react-router.md`。
