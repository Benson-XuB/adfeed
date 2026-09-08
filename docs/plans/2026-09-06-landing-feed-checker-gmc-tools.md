# Landing Feed Checker + Google 拒审只读 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 `deltfu.com` 上线免费营销工具页：① 检查公开 Google Shopping Feed；② 连接 Google 只读并**解释拒审原因**（含 AdFeed 能帮什么）；CTA 指向 waitlist（过审后再改安装 App）。

**Architecture:** 工具页是落地站静态页 + FastAPI 公共 API（不经 Shopify session）。Feed 检查：服务端拉取/解析 XML（限条数），规则打分后丢弃原文不落库。Google 拒审：独立 OAuth（营销站 redirect），token 短时会话（cookie/signed state），调已验证的 Merchant `reports:search`；与审核中 Shopify App / App Home OAuth **隔离**。

**Tech Stack:** `landing-page/` HTML+CSS+JS；`phase0/adfeed` FastAPI；现有 waitlist API；Merchant API + scope `https://www.googleapis.com/auth/content`；nginx 增加 `/tools/*` 静态路由；`deploy-landing-only.sh`。

```
Field contract: docs/plans/2026-08-14-feed-field-contract.md
North Star: docs/plans/2026-08-12-mvp-north-star.md
```

---

## 0. 产品规格（已拍板）

### 0.1 放在哪

| 项 | 决定 |
|----|------|
| URL | `https://deltfu.com/tools` 入口；`/tools/feed-checker`；`/tools/google-issues`（或同页两个 Tab） |
| 表面 | **营销站落地工具**，不是第二个 Shopify App |
| 审核隔离 | **禁止**改审核中 App 隐私/scopes/`shopify app deploy`；可用 landing-only 部署 |

### 0.2 ① Feed Checker

**用户：** 已有 Google Shopping Feed URL（或 XML 文件）的 Shopify/跨境商家。

**做：**

- 粘贴公开 Feed URL **或** 上传 XML（体积上限，如 20MB）
- 解析最多前 **500** 条 `<item>`
- 汇总 + 坏例子（各最多 3 条样例）：
  - 标题过长 / 噪音（属性墙、供应商腔）
  - 缺 `brand` / 脏品牌信号（仅提示，不写回）
  - 服饰常见：`color` / `size` 缺口（有变体语义时）
  - 缺标识：说明「缺 GTIN 应用合规无码路径」——**绝不建议编造 GTIN**
  - 主图缺失
- 免费、**不必登录**
- 文案：诊断语气（「哪里不对」），不要平台黑话

**不做：**

- 读 Shopify Admin 商品
- AI 重写标题 / 自动改 Feed
- 建议假条码、假品牌
- 长期存储整份 Feed

### 0.3 ② 连接 Google → 拒审诊断（免费）

「只读」= **不改**你的 Merchant 商品；**不是**只丢一串错误码。

**用户：** 有 Merchant Center Admin（或足够权限）的商家。

**本版必须有（拒审分析 MVP）：**

1. **拉数据：** Connect Google → OAuth（仅 `auth/content`）→ `reports:search` 拒审/不合格商品（上限如 50 条）+ 汇总计数  
2. **为什么拒审：** 每条/每类展示人话解释，不只 code  
   - 优先用 API 返回的 description / severity  
   - 再加我们的 **原因码词典**（常见码 → 中文/英文短解释）  
   - 例：`policy_enforcement_account_disapproval` → 「这是**账号级政策**问题（如 Misrepresentation），不是单条标题写错；需先在 Merchant Center 处理账号申诉/合规」  
   - 例：缺标识 / 标题 / 品牌类 → 「目录/Feed 字段问题，可用 AdFeed 清理后重新出 Feed」  
3. **用 AdFeed 能帮什么（必写在报告里）：**  
   | 问题类型 | AdFeed 能帮 | AdFeed **不能**替你做 |
   |----------|-------------|------------------------|
   | 脏标题、色/码乱、供应商品牌 | 生成更干净的 Shopping Feed | — |
   | 缺 GTIN | 合规无码路径说明（**绝不编假码**） | — |
   | 账号级政策 / Misrepresentation | 说明需先修 MC 账号 | 不能一键撤销 Google 处罚 |
   | Ads 出价/花费差 | —（后置） | 本版不做代投 |
4. **CTA：** 先看懂原因 → 再「Get early access」（过审后改 Install）  
5. 免费、不扣 generate units  

**后置（你说先放后面的「更深报告分析」）：**

- 趋势图、历史对比、健康分仪表盘  
- Google Ads 花费 / 点击 / ROAS  
- 按类目自动出长文「优化方案」、AI 长报告  
- 写回 Merchant、与 Shopify 店绑定（过审后进 App）

**OAuth 注意：**

- Cloud 客户端增加 redirect：`https://deltfu.com/api/public/google/oauth/callback`（及本地调试 URI）
- 与 App 内 `/api/app/google/...` **路径分开**，避免和审核 App 混用
- Testing 模式：Test users 需含试用邮箱；对外前再走验证

### 0.4 CTA（你已理解）

| 阶段 | 按钮文案（英，与站一致） | 目标 |
|------|--------------------------|------|
| 现在（审核中） | Get early access | `/#waitlist` 或工具页内嵌 waitlist，`source=feed-checker` / `google-issues` |
| 过审后 | Install on Shopify | Partner 安装链接（本计划不实现切换，只预留文案位/配置） |

**顺序：** 诊断（为什么挂）→ AdFeed 能帮什么 → CTA。不要一上来硬推销。  
UTM：`?utm_source=tools&utm_medium=feed-checker` / `google-issues` 等。

### 0.5 与旧 playbook 的差异

`2026-09-06-cold-start-plg-playbook` 曾写检查器 **先不做** 完整 GMC OAuth。  
**2026-09-06 用户决定：① 与 ② 一起做**（未过审不着急，优先营销站）。以本文为准。

### 0.6 成功标准（MVP）

- 公开 Feed URL 能出报告（用 `phase0/feeds/mock-catalog/google-us.xml` 或线上样例自测）
- 测试 Google 账号：拒审码 + **人话原因** + **AdFeed 能帮/不能帮** 区块可见
- CTA 能进 waitlist（`source` 可区分工具）
- 生产仅 landing-only；App Home / 审核面无回归风险

---

## 1. 实现任务

### Task 1: 公共 Feed 检查 API + 单测

**Files:**
- Create: `phase0/adfeed/public_tools/feed_checker.py`
- Create: `phase0/tests/test_public_feed_checker.py`
- Modify: `phase0/adfeed/api.py`（或 `public_router.py` + include）

**Step 1: 写失败测试**

```python
def test_feed_checker_flags_missing_brand_and_long_title():
    xml = b"""<?xml version="1.0"?><rss><channel>
      <item>
        <g:id>1</g:id>
        <title>Supplier Factory Brand Style Color Red Size XL Material Cotton Soft Soft Soft Soft Dress For Women New Arrival Hot Sale</title>
        <g:image_link>https://example.com/a.jpg</g:image_link>
      </item>
    </channel></rss>"""
    report = analyze_feed_bytes(xml, max_items=10)
    assert report["item_count"] == 1
    assert any(b["code"] == "missing_brand" for b in report["buckets"])
    assert not any("invent" in (b.get("advice") or "").lower() for b in report["buckets"])
```

**Step 2:** `pytest phase0/tests/test_public_feed_checker.py -v` → 失败  

**Step 3:** 实现 `analyze_feed_bytes` / `analyze_feed_url`（httpx 拉 URL，超时、只允许 http(s)、限制大小）  

**Step 4:** 测试通过  

**Step 5:** 端点 `POST /api/public/feed-check`：`{ "url": "..." }` 或 multipart file → JSON 报告  

**Step 6: Commit**（仅当用户要求提交时）

---

### Task 2: 营销站 Feed Checker 页

**Files:**
- Create: `landing-page/tools/feed-checker.html`（或 `tools-feed-checker.html` + pretty URL）
- Create: `landing-page/tools/feed-checker.js`
- Modify: `landing-page/styles.css`（复用现有变量，避免新紫色/奶油模板）
- Modify: `landing-page/dev_server.py`（`/tools/feed-checker` 映射）
- Modify: `nginx/deltfu.com.conf`（`location = /tools/feed-checker`）
- Modify: `landing-page/index.html` nav 加 Tools 链接

**Step 1:** 静态页：品牌 + 一句话 + 输入（URL/文件）+ 开始检查 + 报告区 + CTA→`/#waitlist`  

**Step 2:** JS 调 `/api/public/feed-check`，渲染 buckets + 样例  

**Step 3:** 本地 `dev_server.py` + FastAPI 联调 mock XML  

**Step 4:** waitlist `data-source="feed-checker"`  

---

### Task 3: 公共 Google OAuth + 拒审 API（营销站）

**Files:**
- Create: `phase0/adfeed/public_tools/google_oauth.py`
- Create: `phase0/adfeed/public_tools/google_issues.py`
- Create: `phase0/tests/test_public_google_issues.py`
- Modify: `phase0/adfeed/api.py`（路由）
- Modify: `phase0/.env.example` 注释公共 redirect（勿提交真 secret）

**Step 1:** 单测：给定 reports JSON fixture → 展平 issues + **映射人话原因 / AdFeed 相关性标签**（抽取 worktree `issues_from_report_rows`；另加 `issue_copy.py` 词典；**不要**把整棵 App Google 路由拷进生产审核路径）  

**Step 2:**  
- `GET /api/public/google/oauth/start` → redirect Google  
- `GET /api/public/google/oauth/callback` → 设短时 httpOnly cookie（加密 refresh/access 或仅 access+expiry）  
- `GET /api/public/google/issues?merchant_id=&limit=50` → reports.search  
- `POST /api/public/google/logout`  

**Step 3:** Redirect URI 文档化：`https://deltfu.com/api/public/google/oauth/callback`；本地 `http://127.0.0.1:8000/api/public/google/oauth/callback`  

**Step 4:** 速率限制（简单 IP 限流）+ 错误文案（未 registerGcp / 非 Admin）  

---

### Task 4: 营销站 Google Issues 页

**Files:**
- Create: `landing-page/tools/google-issues.html` + `.js`
- Modify: `dev_server.py` / nginx / 首页 nav
- Optional: `landing-page/tools/index.html` 双入口

**Step 1:** Connect Google → 选账号（若多）→ **按原因码汇总** + 表格（商品 / 人话原因 / AdFeed 能否帮）  

**Step 2:** 报告区固定 **How AdFeed helps**（能帮 / 不能帮）；再 CTA waitlist `source=google-issues`  

**Step 3:** 页脚：免费只读诊断；不改 Merchant；不连 Shopify；账号级问题需先在 MC 处理  

---

### Task 5: 部署与验收（landing-only）

**Files:**
- Modify: `phase0/scripts/prod/deploy-landing-only.sh`（若需带上新 API 文件 / nginx）

**Step 1:** 确认脚本会同步 `api` 公共路由 + `landing-page/tools/*` + nginx  

**Step 2:** 部署后验收：

- [ ] `https://deltfu.com/tools/feed-checker` 200  
- [ ] 用公开 XML 出报告  
- [ ] Google 连接（Test user）出拒审抽样  
- [ ] waitlist 提交成功且 source 正确  
- [ ] `?shop=` App Home 仍走嵌入 App，未误伤  

**Step 3:** 首页加一处「Free Feed Checker」链到工具（非 hero 堆砌：nav 或 How 区一条即可）  

---

### Task 6: 文档收尾

**Files:**
- Modify: `docs/plans/2026-09-06-cold-start-plg-playbook.md`（P0 指向本文；注明 ①② 同做）
- Create: 可选短 HTML 线框（非必须）

---

## 2. 明确不做（本计划）

- 第二个 Shopify App  
- 审核期改生产 App 隐私 / Partner Google 声明  
- Ads 指标、写 Merchant、假 GTIN 建议  
- 工具矩阵（Meta/TikTok checker 等）  

---

## 3. 执行顺序建议

1 → 2（先有可分享的 Feed 检查链接）→ 3 → 4 → 5 → 6  

① 与 ② **同一计划内完成**，但发布可先发 Feed Checker 再开 Google（若 OAuth 客户端 redirect 未就绪）。

---

## 4. 你需要准备的（非代码）

- [ ] Cloud OAuth Client 增加 `https://deltfu.com/api/public/google/oauth/callback`  
- [ ] 生产 `.env` 已有 `GOOGLE_OAUTH_*`（可与开发同一 Client；redirect 用环境变量区分）  
- [ ] Test users 含试用邮箱  
- [ ] （可选）过审后把 CTA 配置改成 Install URL  

---

**状态：** IMPLEMENTED (working tree) — 待本地联调 / landing-only 部署；生产 OAuth 需加 public redirect。
