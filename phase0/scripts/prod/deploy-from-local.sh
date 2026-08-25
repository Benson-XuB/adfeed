#!/usr/bin/env bash
# AdFeed AI — build on Mac, rsync to VPS, restart services.
#
# Usage:
#   SERVER=47.237.157.77 SSH_USER=admin SSH_IDENTITY=~/.ssh/adfeed_deploy \
#     ./phase0/scripts/prod/deploy-from-local.sh
#   ... --backend-only
#   ... --no-build

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE0="$(cd "$SCRIPT_DIR/../.." && pwd)"
WEB="${PHASE0}/add-feed-ai/web"

SERVER="${SERVER:-deltfu.com}"
SSH_USER="${SSH_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/opt/adfeed}"
SSH_IDENTITY="${SSH_IDENTITY:-}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)
if [[ -n "$SSH_IDENTITY" ]]; then
  SSH_OPTS+=(-i "$SSH_IDENTITY" -o IdentitiesOnly=yes)
fi
SSH_TARGET="${SSH_USER}@${SERVER}"
RSYNC_RSH="ssh ${SSH_OPTS[*]}"

ssh_cmd() { ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$@"; }

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

if ! ssh_cmd 'echo ssh-ok' >/dev/null 2>&1; then
  echo "ERROR: cannot SSH to ${SSH_TARGET}. Check key, user, and firewall."
  exit 1
fi

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
ssh_cmd 'sudo systemctl stop adfeed-web 2>/dev/null || true; sudo swapoff /swapfile 2>/dev/null && sudo swapon /swapfile 2>/dev/null || true; echo prep ok'

echo ""
echo "━━━ [3/5] git pull on server ━━━"
ssh_cmd "sudo git config --global --add safe.directory ${REMOTE_DIR}; cd ${REMOTE_DIR} && sudo git fetch origin && sudo git reset --hard origin/main && sudo chown -R adfeed:adfeed ${REMOTE_DIR}"

echo ""
echo "━━━ [4/5] Sync artifacts ━━━"
if [[ "$BACKEND_ONLY" == false ]]; then
  ssh_cmd "sudo mkdir -p ${REMOTE_DIR}/phase0/add-feed-ai/web/build && sudo chown -R ${SSH_USER}:${SSH_USER} ${REMOTE_DIR}/phase0/add-feed-ai/web"
  rsync -avz --delete -e "$RSYNC_RSH" \
    "${WEB}/build/" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/build/"
  rsync -avz -e "$RSYNC_RSH" \
    "${WEB}/package.json" "${WEB}/package-lock.json" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/"
  rsync -avz -e "$RSYNC_RSH" \
    "${WEB}/prisma/" \
    "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/prisma/"
  ssh_cmd "sudo chown -R adfeed:adfeed ${REMOTE_DIR}/phase0/add-feed-ai/web && cd ${REMOTE_DIR}/phase0/add-feed-ai/web && sudo -u adfeed npm ci --omit=dev && sudo -u adfeed npx prisma generate && sudo -u adfeed npx prisma migrate deploy"
fi

ssh_cmd "sudo -u adfeed ${REMOTE_DIR}/.venv/bin/pip install -q -r ${REMOTE_DIR}/phase0/requirements.txt"

echo ""
echo "━━━ [5/5] Nginx + restart ━━━"
ssh_cmd 'sudo bash -s' <<'ENDSSH'
set -euo pipefail
if [[ -f /opt/adfeed/nginx/deltfu.com.conf ]]; then
  install -d /etc/nginx/snippets
  cp /opt/adfeed/nginx/deltfu-feeds.conf /etc/nginx/snippets/deltfu-feeds.conf
  cp /opt/adfeed/nginx/deltfu.com.conf /etc/nginx/sites-available/deltfu.com
  ln -sf /etc/nginx/sites-available/deltfu.com /etc/nginx/sites-enabled/deltfu.com
  rm -f /etc/nginx/conf.d/deltfu-feeds.conf
fi
nginx -t && systemctl reload nginx
bash /opt/adfeed/phase0/scripts/prod/install-systemd.sh
systemctl restart adfeed-api
systemctl restart adfeed-web
sleep 2
systemctl status adfeed-api --no-pager -l | head -8
echo "---"
systemctl status adfeed-web --no-pager -l | head -8
ENDSSH

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Deploy complete"
echo "  App:  http://${SERVER}/"
echo "  API:  http://${SERVER}/api/health"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
