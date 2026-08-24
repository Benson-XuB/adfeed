#!/usr/bin/env bash
# AdFeed AI — build on Mac, rsync to VPS, restart services.
#
# Usage (from repo root or phase0/):
#   ./phase0/scripts/prod/deploy-from-local.sh
#   ./phase0/scripts/prod/deploy-from-local.sh --backend-only
#   ./phase0/scripts/prod/deploy-from-local.sh --no-build   # reuse local web/build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE0="$(cd "$SCRIPT_DIR/../.." && pwd)"
WEB="${PHASE0}/add-feed-ai/web"
REPO_ROOT="$(cd "$PHASE0/.." && pwd)"

SERVER="${SERVER:-deltfu.com}"
SSH_USER="${SSH_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/opt/adfeed}"
SSH_TARGET="${SSH_USER}@${SERVER}"

NO_BUILD=false
BACKEND_ONLY=false
for arg in "$@"; do
  case "$arg" in
    --no-build) NO_BUILD=true ;;
    --backend-only) BACKEND_ONLY=true ;;
  esac
done

echo "┌────────────────────────────────────────┐"
echo "│  AdFeed AI — local build & deploy"
echo "│  Target: ${SSH_TARGET}:${REMOTE_DIR}"
echo "└────────────────────────────────────────┘"

if ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$SSH_TARGET" 'echo ssh-ok' >/dev/null 2>&1; then
  echo "ERROR: cannot SSH to ${SSH_TARGET}. Check key, user, and firewall."
  exit 1
fi

# ── local web build ──
if [[ "$BACKEND_ONLY" == false && "$NO_BUILD" == false ]]; then
  echo ""
  echo "━━━ [1/5] Building React Router web locally ━━━"
  cd "$WEB"
  npm ci
  npm run setup
  npm run build
  echo "  → ${WEB}/build ready"
fi

echo ""
echo "━━━ [2/5] Stop web + prep server ━━━"
ssh "$SSH_TARGET" <<ENDSSH
  systemctl stop adfeed-web 2>/dev/null || true
  swapoff /swapfile 2>/dev/null && swapon /swapfile 2>/dev/null || true
  echo prep ok
ENDSSH

echo ""
echo "━━━ [3/5] git pull on server ━━━"
ssh "$SSH_TARGET" "cd ${REMOTE_DIR} && git fetch origin && git reset --hard origin/main && chown -R adfeed:adfeed ${REMOTE_DIR}"

echo ""
echo "━━━ [4/5] Sync artifacts ━━━"
if [[ "$BACKEND_ONLY" == false ]]; then
  rsync -avz --delete \
    "${WEB}/build/" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/build/"
  rsync -avz \
    "${WEB}/package.json" "${WEB}/package-lock.json" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/"
  rsync -avz \
    "${WEB}/prisma/" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/prisma/"
  ssh "$SSH_TARGET" <<ENDSSH
    cd ${REMOTE_DIR}/phase0/add-feed-ai/web
    sudo -u adfeed npm ci --omit=dev
    sudo -u adfeed npx prisma generate
    sudo -u adfeed npx prisma migrate deploy
    chown -R adfeed:adfeed ${REMOTE_DIR}/phase0/add-feed-ai/web
ENDSSH
fi

ssh "$SSH_TARGET" <<ENDSSH
  ${REMOTE_DIR}/.venv/bin/pip install -q -r ${REMOTE_DIR}/phase0/requirements.txt
ENDSSH

echo ""
echo "━━━ [5/5] Nginx + restart ━━━"
ssh "$SSH_TARGET" <<'ENDSSH'
  if [[ -f /opt/adfeed/nginx/deltfu.com.conf ]]; then
    cp /opt/adfeed/nginx/deltfu.com.conf /etc/nginx/sites-available/deltfu.com
    ln -sf /etc/nginx/sites-available/deltfu.com /etc/nginx/sites-enabled/deltfu.com
    cp /opt/adfeed/nginx/deltfu-feeds.conf /etc/nginx/conf.d/deltfu-feeds.conf
  fi
  nginx -t && systemctl reload nginx
  systemctl daemon-reload
  systemctl restart adfeed-api
  systemctl restart adfeed-web
  sleep 2
  systemctl status adfeed-api --no-pager -l | head -6
  echo "---"
  systemctl status adfeed-web --no-pager -l | head -6
ENDSSH

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy complete"
echo "  App:  https://${SERVER}/app"
echo "  API:  https://${SERVER}/api/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
