#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────────────────────
#  AdFeed AI — 本地构建 + rsync 推送到服务器
#  ──────────────────────────────────────────────────────────────
#
#  配置（修改下面这行）：
SERVER="deltfu.com"          # 你的服务器地址
SSH_USER="admin"             # SSH 用户名
REMOTE_DIR="/opt/adfeed"     # 服务器上项目目录
#
#  用法（在本机 Mac 上执行）：
#    ./deploy-from-local.sh                        # 完整部署（旧 Next.js web）
#    ./deploy-from-local.sh --no-build             # 跳过本地构建（.next 已存在）
#    ./deploy-from-local.sh --backend-only         # 只更新后端 Python 代码
#
#  2026-08 iframe 说明：
#  - 商家入口已改为 add-feed-ai/web（React Router），不再依赖 phase0/web Next.js。
#  - 生产还需在服务器上跑 React Router（`npm run start` / systemd），并把
#    shopify.app.toml application_url 指到该进程（见 shopify.app.toml.prod-backup）。
#  - FastAPI 仍用本脚本 --backend-only 即可；若 SSH 超时，先修网络/密钥再部署。
#  ──────────────────────────────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
NO_BUILD=false
BACKEND_ONLY=false

for arg in "$@"; do
    case "$arg" in
        --no-build) NO_BUILD=true ;;
        --backend-only) BACKEND_ONLY=true ;;
    esac
done

echo "┌────────────────────────────────────────┐"
echo "│  AdFeed AI — Local Build & Deploy     │"
echo "│  Target: ${SSH_USER}@${SERVER}:${REMOTE_DIR}  │"
echo "└────────────────────────────────────────┘"

# Fail fast if SSH is unreachable (common: firewall / wrong key)
if ! ssh -o BatchMode=yes -o ConnectTimeout=12 "${SSH_USER}@${SERVER}" 'echo ssh-ok' >/dev/null 2>&1; then
    echo "ERROR: cannot SSH to ${SSH_USER}@${SERVER} (timeout or auth)."
    echo "Fix network/SSH key before deploy. Backend-only and React Router cutover blocked until then."
    exit 1
fi

# ── Step 1: 本地构建 Next.js ──
if [ "$BACKEND_ONLY" = false ] && [ "$NO_BUILD" = false ]; then
    echo ""
    echo "━━━ [1/5] Building Next.js locally (your Mac has enough RAM) ━━━"
    cd "$SCRIPT_DIR/web"
    npm run build
    echo "  → .next is ready"
fi

# ── Step 2: 服务器上备份旧 .next 并删除 ──
echo ""
echo "━━━ [2/5] Preparing server ━━━"
ssh "${SSH_USER}@${SERVER}" <<'ENDSSH'
    sudo systemctl stop adfeed-web 2>/dev/null || true
    # 清理旧构建（释放 inode / 空闲空间）
    if [ -d /opt/adfeed/phase0/web/.next ]; then
        rm -f /opt/adfeed/phase0/web/.next.old
        cp -a /opt/adfeed/phase0/web/.next /opt/adfeed/phase0/web/.next.old 2>/dev/null || true
        rm -rf /opt/adfeed/phase0/web/.next
    fi
    # 释放 swap 碎片
    sudo swapoff /swapfile 2>/dev/null && sudo swapon /swapfile 2>/dev/null || true
    echo "prep done"
ENDSSH

# ── Step 3: 服务器 git pull ──
echo ""
echo "━━━ [3/5] Pulling latest code on server ━━━"
ssh "${SSH_USER}@${SERVER}" "cd ${REMOTE_DIR} && sudo git fetch origin && sudo git reset --hard origin/main"

# ── Step 4: rsync 本地构建产物到服务器 ──
if [ "$BACKEND_ONLY" = false ]; then
    echo ""
    echo "━━━ [4/5] rsync .next to server ━━━"
    rsync -avz --delete "$SCRIPT_DIR/web/.next/" "${SSH_USER}@${SERVER}:${REMOTE_DIR}/phase0/web/.next/"
    echo "  → .next synced"
fi

# ── Step 5: 部署 Nginx 上传优化配置 ──
echo ""
echo "━━━ [5/6] Deploying Nginx config ━━━"
ssh "${SSH_USER}@${SERVER}" <<'ENDSSH'
    # 检查是否已有 proxy_request_buffering 配置
    if ! grep -q 'proxy_request_buffering off' /etc/nginx/sites-enabled/deltfu.com 2>/dev/null; then
        sudo sed -i '/proxy_pass http:\/\/127.0.0.1:8000/a \        proxy_request_buffering off;' /etc/nginx/sites-enabled/deltfu.com
        echo "  → added proxy_request_buffering off"
    else
        echo "  → proxy_request_buffering already configured"
    fi
    # 确保 client_max_body_size 200M
    if ! grep -q 'client_max_body_size 200M' /etc/nginx/sites-enabled/deltfu.com 2>/dev/null; then
        sudo sed -i '/server {/a \    client_max_body_size 200M;' /etc/nginx/sites-enabled/deltfu.com
        echo "  → added client_max_body_size 200M"
    else
        echo "  → client_max_body_size already configured"
    fi
    sudo nginx -t && sudo systemctl reload nginx
    echo "  → nginx reloaded"
ENDSSH

# ── Step 6: 重启服务 ──
echo ""
echo "━━━ [6/6] Restarting services ━━━"
ssh "${SSH_USER}@${SERVER}" <<ENDSSH
    # 确保 .next 权限正确
    if [ -d ${REMOTE_DIR}/phase0/web/.next ]; then
        sudo chown -R adfeed:adfeed ${REMOTE_DIR}/phase0/web/.next
    fi
    # 删除可能的旧 webapp.db
    rm -f ${REMOTE_DIR}/phase0/data/webapp.db
    # daemon-reload（service 文件可能有更新）
    sudo systemctl daemon-reload
    # 重启
    sudo systemctl restart adfeed-api
    sudo systemctl restart adfeed-web
    sleep 2
    sudo systemctl status adfeed-api --no-pager -l | head -5
    echo "---"
    sudo systemctl status adfeed-web --no-pager -l | head -5
ENDSSH

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy complete!"
echo "  Frontend: https://${SERVER}"
echo "  API docs: https://${SERVER}/docs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
