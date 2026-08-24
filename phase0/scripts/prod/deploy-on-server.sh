#!/usr/bin/env bash
# AdFeed AI — deploy on the VPS (git pull + deps + build + restart).
#
# On a 2C2G box, prefer building the web app on your Mac:
#   phase0/deploy-from-local.sh
#
# Usage (on server):
#   bash /opt/adfeed/phase0/scripts/prod/deploy-on-server.sh
#   bash .../deploy-on-server.sh --skip-web-build   # after local rsync of web/build
#   bash .../deploy-on-server.sh --backend-only

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/adfeed}"
PHASE0="${INSTALL_DIR}/phase0"
WEB="${PHASE0}/add-feed-ai/web"
VENV="${INSTALL_DIR}/.venv"
APP_USER="${APP_USER:-adfeed}"

SKIP_WEB_BUILD=false
BACKEND_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --skip-web-build) SKIP_WEB_BUILD=true ;;
    --backend-only) BACKEND_ONLY=true; SKIP_WEB_BUILD=true ;;
  esac
done

run_as_app() {
  if [[ "$(id -un)" == "$APP_USER" ]]; then
    "$@"
  else
    sudo -u "$APP_USER" "$@"
  fi
}

echo "┌────────────────────────────────────────┐"
echo "│  AdFeed AI — server deploy"
echo "└────────────────────────────────────────┘"

cd "$INSTALL_DIR"
if [[ -d .git ]]; then
  echo "━━━ git pull ━━━"
  run_as_app git pull origin main
fi

echo "━━━ Python deps ━━━"
run_as_app "$VENV/bin/pip" install -q -r "${PHASE0}/requirements.txt"

if [[ "$BACKEND_ONLY" == false ]]; then
  echo "━━━ Web deps + Prisma ━━━"
  cd "$WEB"
  run_as_app npm ci --omit=dev

  if [[ "$SKIP_WEB_BUILD" == false ]]; then
    echo "━━━ Web build (needs ~1.5GB RAM; use deploy-from-local.sh if OOM) ━━━"
    run_as_app env NODE_OPTIONS=--max-old-space-size=1536 npm run setup
    run_as_app env NODE_OPTIONS=--max-old-space-size=1536 npm run build
  else
    echo "━━━ Prisma migrate only (web build skipped) ━━━"
    run_as_app npx prisma generate
    run_as_app npx prisma migrate deploy
  fi
fi

echo "━━━ Restart services ━━━"
if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  systemctl restart adfeed-api
  [[ "$BACKEND_ONLY" == false ]] && systemctl restart adfeed-web
  systemctl status adfeed-api --no-pager -l | head -8
  [[ "$BACKEND_ONLY" == false ]] && systemctl status adfeed-web --no-pager -l | head -8
else
  sudo systemctl restart adfeed-api
  [[ "$BACKEND_ONLY" == false ]] && sudo systemctl restart adfeed-web
fi

if systemctl is-active --quiet nginx 2>/dev/null; then
  sudo nginx -t && sudo systemctl reload nginx
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy complete"
echo "  Health: curl -fsS https://deltfu.com/api/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
