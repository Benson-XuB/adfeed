#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────
#  AdFeed AI — 生产环境 Git Pull + 重启（后端）
#  ──────────────────────────────────────
#  注意：前端 .next 必须通过 deploy-from-local.sh 从 Mac 推送。
#  此脚本仅处理后端代码拉取 + 重启。
#
#  在服务器上执行：
#    ./deploy.sh              # 拉取最新代码 + 重启后端
#    ./deploy.sh pull-only    # 只拉代码不重启

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-all}"

# ── Step 1: 拉取最新代码 ──
pull() {
    echo ""
    echo "━━━ Pulling latest code from GitHub ━━━"
    cd "$SCRIPT_DIR"
    git pull origin main
}

# ── Step 2: 安装 Python 依赖（避免 big 文件重新安装慢） ──
install_python_deps() {
    echo ""
    echo "━━━ Updating Python deps ━━━"
    pip install -r requirements.txt --quiet
}

# ── Step 3: 重启后端（FastAPI） ──
restart_backend() {
    echo ""
    echo "━━━ Restarting FastAPI backend ━━━"

    # 如果通过 systemd 管理
    if [ -f /etc/systemd/system/adfeed-api.service ]; then
        echo "  → restarting via systemd..."
        sudo systemctl restart adfeed-api
        sudo systemctl status adfeed-api --no-pager
        return
    fi

    # 否则 pm2 / 手动
    if command -v pm2 &>/dev/null; then
        echo "  → restarting via pm2..."
        pm2 restart adfeed-api 2>/dev/null || pm2 start "$SCRIPT_DIR/server.py" \
            --name adfeed-api \
            --interpreter python3 \
            --cwd "$SCRIPT_DIR"
        pm2 save
        return
    fi

    # 最后的兜底：直接杀进程重启
    echo "  → killing old process on port 8000..."
    PIDS=$(lsof -ti :8000 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null || true
        sleep 2
    fi
    echo "  → starting FastAPI on port 8000..."
    cd "$SCRIPT_DIR"
    nohup python3 server.py > /tmp/adfeed-api.log 2>&1 &
    echo "  → PID: $!"
}

# ── Step 5: 重启前端（Next.js） ──
restart_frontend() {
    echo ""
    echo "━━━ Restarting Next.js frontend ━━━"

    if [ -f /etc/systemd/system/adfeed-web.service ]; then
        echo "  → restarting via systemd..."
        sudo systemctl restart adfeed-web
        sudo systemctl status adfeed-web --no-pager
        return
    fi

    if command -v pm2 &>/dev/null; then
        echo "  → restarting via pm2..."
        pm2 restart adfeed-web 2>/dev/null || pm2 start npm \
            --name adfeed-web \
            -- run start \
            --cwd "$SCRIPT_DIR/web"
        pm2 save
        return
    fi

    echo "  → killing old process on port 3000..."
    PIDS=$(lsof -ti :3000 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        kill $PIDS 2>/dev/null || true
        sleep 2
    fi
    echo "  → starting Next.js on port 3000..."
    cd "$SCRIPT_DIR/web"
    nohup npm run start > /tmp/adfeed-web.log 2>&1 &
    echo "  → PID: $!"
}

# ── Step 6: 重载 Nginx（如有配置变更） ──
reload_nginx() {
    if systemctl is-active --quiet nginx 2>/dev/null; then
        echo ""
        echo "━━━ Reloading Nginx ━━━"
        sudo nginx -t && sudo systemctl reload nginx
    fi
}

# ══════════════════════════════════════

case "$TARGET" in
    all|backend)
        pull
        install_python_deps
        restart_backend
        ;;
    pull-only)
        pull
        ;;
    *)
        echo "用法: $0 [all|pull-only]"
        echo ""
        echo "前端 .next 构建占用内存大，请在 Mac 本地运行："
        echo "  ./deploy-from-local.sh"
        exit 1
        ;;
esac

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Backend deploy complete"
echo "  API docs: https://deltfu.com/docs"
echo ""
echo "  前端如需更新，Mac 本地执行："
echo "    ./deploy-from-local.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
