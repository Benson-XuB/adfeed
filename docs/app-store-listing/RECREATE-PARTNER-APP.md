# 重建 Partner 应用（config link，不推倒代码库）

适用：Dev Dashboard 有应用，但 Partner → 应用分发 → 所有应用 **列表为空**，Support 无法恢复旧 app。

旧 `client_id`（作废前备份）：`ac2bf432a87c7e12cb7c439556fe762b`

---

## 原则

1. **代码库不动** — 只换 Shopify 上的 app 记录 + 本地/服务器凭证。
2. **从 Partner org 创建** — 不要只在 Dev Dashboard 随便点 Create app。
3. **先确认 Partner 能看到新 app，再删旧的**。
4. 分发方式（Public / Custom）**选定后不能改**；要上 App Store 必须选 **Public**。

---

## 0. 备份

```bash
cd phase0/add-feed-ai
cp shopify.app.toml shopify.app.toml.before-relink
cp -a ../scripts/prod/.secrets ../scripts/prod/.secrets.before-relink 2>/dev/null || true
```

记下旧 app 的 Dev URL（删前对照）：
`https://dev.shopify.com/dashboard/228869571/apps/405095612417`

---

## 1. 用 Partner 账号登录 CLI

在**本机终端**（必须可交互，不能是 CI）：

```bash
shopify auth logout
shopify auth login
```

- 选 **Partner 账号**（`partners.shopify.com/5125411` 对应的那个）
- **不要**选店铺后台账号

可选：浏览器打开 Partner → 应用分发 → **访问 Dev Dashboard**，确认跳转后左上角 org 名是你自己的 Partner org。

---

## 2. 链接到新应用（config link）

**已用 CLI 完成（2026-08-29）：**

```bash
# 在临时目录创建新 app（非交互）
shopify app init --name "AdFeed AI 2" --organization-id 228869571 --template none -d npm -p /tmp/adfeed-shopify-new-app

# 主项目链接新 client_id
cd phase0/add-feed-ai
shopify app config link --client-id 717a420399ce99ea368c8deca3ec25ff --force --file-name shopify.app.toml

# 恢复 shopify.app.toml 里的 deltfu.com / webhooks / scopes（见仓库当前文件）
shopify app deploy --allow-updates --version adfeed-ai-1 --message "fresh partner-linked app"

# 拉凭证到本地（勿覆盖生产 BACKEND_URL）
shopify app env show
```

手动流程（若需重来）：

```bash
cd phase0/add-feed-ai
shopify app config link
```

| 提示 | 选什么 |
|------|--------|
| Create new app / Link existing | **Create new app** |
| App name | `AdFeed AI`（或 `AdFeed AI` 若重名则 `AdFeed AI 2`） |
| App type / distribution（若 CLI 询问） | **Public**（要上 App Store） |

完成后 CLI 会改写 `shopify.app.toml` 里的 `client_id`。

**立刻检查** `shopify.app.toml` 仍是生产 URL（`config link` 有时会改乱）：

```toml
application_url = "https://deltfu.com"

[auth]
redirect_urls = [
  "https://deltfu.com/auth/callback",
  "https://deltfu.com/api/shopify/callback"
]
```

若被改成 tunnel / localhost，改回上表，保存后再 deploy。

---

## 3. 抄新凭证

Dev Dashboard → 新 **AdFeed AI** → **应用设置（Settings）**：

- **Client ID**
- **Client secret**（只显示一次，立刻保存）

---

## 4. 更新本地 secrets（3 处）

### `phase0/scripts/prod/.secrets/phase0.env`

```env
SHOPIFY_CLIENT_ID=<新 Client ID>
SHOPIFY_CLIENT_SECRET=<新 Client secret>
```

### `phase0/scripts/prod/.secrets/web.env`

```env
SHOPIFY_API_KEY=<新 Client ID>
SHOPIFY_API_SECRET=<新 Client secret>
```

### 本地开发（若有 `phase0/.env`、`phase0/add-feed-ai/web/.env`）

同样更新 `SHOPIFY_CLIENT_ID` / `SHOPIFY_CLIENT_SECRET`（FastAPI）和 `SHOPIFY_API_KEY` / `SHOPIFY_API_SECRET`（React Router web）。

---

## 5. 部署 app 配置到 Shopify

```bash
cd phase0/add-feed-ai
shopify app deploy --allow-updates --version adfeed-ai-1 --message "fresh partner-linked app"
```

确认 release 成功，Dev Dashboard → 版本 里新版本为 **有效**。

---

## 6. 推凭证到生产服务器

项目里正确的 SSH 配置（不是 `root@deltfu.com`）：

```bash
SERVER=47.237.157.77 SSH_USER=admin SSH_IDENTITY=~/.ssh/adfeed_deploy \
  bash phase0/scripts/prod/configure-and-deploy.sh
```

或只更新 env + 重启：

```bash
scp -i ~/.ssh/adfeed_deploy phase0/scripts/prod/.secrets/phase0.env admin@47.237.157.77:/tmp/
scp -i ~/.ssh/adfeed_deploy phase0/scripts/prod/.secrets/web.env admin@47.237.157.77:/tmp/
ssh -i ~/.ssh/adfeed_deploy admin@47.237.157.77 \
  'sudo mv /tmp/phase0.env /opt/adfeed/phase0/.env && sudo mv /tmp/web.env /opt/adfeed/phase0/add-feed-ai/web/.env && sudo chown adfeed:adfeed /opt/adfeed/phase0/.env /opt/adfeed/phase0/add-feed-ai/web/.env && sudo chmod 600 /opt/adfeed/phase0/.env /opt/adfeed/phase0/add-feed-ai/web/.env && sudo systemctl restart adfeed-api adfeed-web'
```

完整部署（含 web build）：

```bash
SERVER=47.237.157.77 SSH_USER=admin SSH_IDENTITY=~/.ssh/adfeed_deploy \
  bash phase0/scripts/prod/deploy-from-local.sh
```

---

## 7. Partner 选分发方式

1. https://partners.shopify.com/5125411/apps
2. **应用分发 → 所有应用** — 应出现新 **AdFeed AI**
3. 点应用 → **Choose distribution** → **Public distribution** → Select
4. **Manage listing** — 按 `SUBMIT-TODAY.md` 填文案和截图
5. Testing instructions — 整份粘贴 `TESTING.md`
6. 测试店 **卸载旧 app → 安装新 app**（OAuth 会绑新 client_id）
7. Plans / 生成 feed 走通后 → **Submit for review**

若 **所有应用仍为空**：说明 config link 时登录的不是 Partner org → 回到步骤 1，或换浏览器无痕重登。

---

## 8. 删旧 app（仅在新 app 全通后）

Dev Dashboard → 旧 AdFeed AI（`405095612417` / 旧 client_id）→ 删除。

删前确认：

- [ ] Partner 列表里有新 app
- [ ] 已选 Public distribution
- [ ] `shopify app deploy` 成功
- [ ] 生产 `https://deltfu.com/api/health` 正常
- [ ] 测试店用新 app 能打开 App Home、生成 feed

---

## 9. 验收清单

```bash
# 生产健康
curl -fsS https://deltfu.com/api/health

# listing 自检（文案/截图尺寸）
python3 docs/app-store-listing/self_test.py
```

Admin 内：

- [ ] 嵌入式 App Home（Home / Plans）正常
- [ ] Confirm brand → Generate → Copy feed URL
- [ ] Plans → Switch to Starter → 批准 charge
- [ ] Webhook 失败率在 Dev Dashboard 监控里下降（安装后观察几小时）

---

## 常见问题

**Q: `config link` 后 scopes / webhooks 丢了？**  
A: 以仓库里 `shopify.app.toml` 为准，改回后重新 `shopify app deploy`。

**Q: 测试店还连着旧 app？**  
A: 店铺 Admin → 应用 → 卸载 AdFeed AI → 从 Partner 预览链接或 Dev「安装应用」重装。

**Q: FastAPI 和 React Router 都要新 secret 吗？**  
A: 要。FastAPI 用 `SHOPIFY_CLIENT_ID/SECRET`；web 用 `SHOPIFY_API_KEY/SECRET`（同一对值，变量名不同）。

**Q: 硬编码的旧 client_id 脚本？**  
A: `phase0/get_shopify_token.py`、`phase0/exchange_legacy_token.py`、`docs/app-store-listing/capture_live_screenshots.sh` 里有旧 ID，按需改或改用 env。
