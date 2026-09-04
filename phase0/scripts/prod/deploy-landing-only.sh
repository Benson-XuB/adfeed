#!/usr/bin/env bash
# Deploy marketing landing + waitlist ONLY.
# Does NOT rebuild/restart the Shopify embedded web app (review-safe).
#
# Usage:
#   SERVER=47.237.157.77 SSH_USER=admin SSH_IDENTITY=~/.ssh/adfeed_deploy \
#     bash phase0/scripts/prod/deploy-landing-only.sh
#
# What it updates:
#   - /opt/adfeed/landing-page/  (static marketing)
#   - nginx site (shop/host still → React App Home)
#   - phase0/adfeed/api.py + db.py from the landing commit (waitlist only)
#   - restart adfeed-api only
#
# What it does NOT touch:
#   - add-feed-ai/web build
#   - adfeed-web service
#   - feed_quality / store_db / billing App fixes (stay on main until full deploy)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PHASE0="$REPO/phase0"

SERVER="${SERVER:-47.237.157.77}"
SSH_USER="${SSH_USER:-admin}"
REMOTE_DIR="${REMOTE_DIR:-/opt/adfeed}"
SSH_IDENTITY="${SSH_IDENTITY:-$HOME/.ssh/adfeed_deploy}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=15)
if [[ -n "$SSH_IDENTITY" ]]; then
  SSH_OPTS+=(-i "$SSH_IDENTITY" -o IdentitiesOnly=yes)
fi
SSH_TARGET="${SSH_USER}@${SERVER}"
RSYNC_RSH="ssh ${SSH_OPTS[*]}"

ssh_cmd() { ssh "${SSH_OPTS[@]}" "$SSH_TARGET" "$@"; }

# Prefer the dedicated landing/waitlist commit (no App fix hunks in api.py).
LANDING_COMMIT="${LANDING_COMMIT:-}"
if [[ -z "$LANDING_COMMIT" ]]; then
  LANDING_COMMIT="$(git -C "$REPO" log --oneline --grep='waitlist signup, and safe nginx split' -n 1 --format=%H || true)"
fi
if [[ -z "$LANDING_COMMIT" ]]; then
  echo "ERROR: cannot find landing/waitlist commit. Set LANDING_COMMIT=<sha>."
  exit 1
fi

echo "┌────────────────────────────────────────┐"
echo "│  Landing-only deploy (review-safe)"
echo "│  Target: ${SSH_TARGET}:${REMOTE_DIR}"
echo "│  API src commit: ${LANDING_COMMIT:0:10}"
echo "└────────────────────────────────────────┘"

if ! ssh_cmd 'echo ssh-ok' >/dev/null 2>&1; then
  echo "ERROR: cannot SSH to ${SSH_TARGET}"
  exit 1
fi

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
git -C "$REPO" show "${LANDING_COMMIT}:phase0/adfeed/api.py" >"$TMP/api.py"
git -C "$REPO" show "${LANDING_COMMIT}:phase0/adfeed/db.py" >"$TMP/db.py"

echo ""
echo "━━━ [1/4] Sync landing-page ━━━"
ssh_cmd "sudo mkdir -p ${REMOTE_DIR}/landing-page && sudo chown -R ${SSH_USER}:${SSH_USER} ${REMOTE_DIR}/landing-page"
rsync -avz --delete -e "$RSYNC_RSH" \
  --exclude '.DS_Store' \
  --exclude 'dev_server.py' \
  "${REPO}/landing-page/" \
  "${SSH_TARGET}:${REMOTE_DIR}/landing-page/"
ssh_cmd "sudo chown -R adfeed:adfeed ${REMOTE_DIR}/landing-page"

echo ""
echo "━━━ [2/4] Sync waitlist-only api.py + db.py ━━━"
rsync -avz -e "$RSYNC_RSH" \
  "$TMP/api.py" \
  "${SSH_TARGET}:/tmp/adfeed-api.waitlist.py"
rsync -avz -e "$RSYNC_RSH" \
  "$TMP/db.py" \
  "${SSH_TARGET}:/tmp/adfeed-db.waitlist.py"
ssh_cmd "sudo cp /tmp/adfeed-api.waitlist.py ${REMOTE_DIR}/phase0/adfeed/api.py && sudo cp /tmp/adfeed-db.waitlist.py ${REMOTE_DIR}/phase0/adfeed/db.py && sudo chown adfeed:adfeed ${REMOTE_DIR}/phase0/adfeed/api.py ${REMOTE_DIR}/phase0/adfeed/db.py"

echo ""
echo "━━━ [3/4] Nginx (landing vs App Home split) ━━━"
if [[ -f "${REPO}/nginx/deltfu.com.conf" ]]; then
  rsync -avz -e "$RSYNC_RSH" \
    "${REPO}/nginx/deltfu.com.conf" "${REPO}/nginx/deltfu-feeds.conf" \
    "${SSH_TARGET}:/tmp/"
  ssh_cmd 'sudo bash -s' <<'ENDSSH'
set -euo pipefail
install -d /etc/nginx/snippets
cp /tmp/deltfu-feeds.conf /etc/nginx/snippets/deltfu-feeds.conf
cp /tmp/deltfu.com.conf /etc/nginx/sites-available/deltfu.com
ln -sf /etc/nginx/sites-available/deltfu.com /etc/nginx/sites-enabled/deltfu.com
nginx -t && systemctl reload nginx
ENDSSH
fi

echo ""
echo "━━━ [4/4] Restart API only (not adfeed-web) ━━━"
ssh_cmd 'sudo systemctl restart adfeed-api && sleep 2 && systemctl is-active adfeed-api && curl -fsS http://127.0.0.1:8000/api/health && echo && curl -fsS -X POST http://127.0.0.1:8000/api/waitlist -H "Content-Type: application/json" -d "{\"email\":\"deploy-smoke@example.com\",\"source\":\"deploy-smoke\"}"'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Landing-only deploy complete"
echo "  Marketing: https://deltfu.com/"
echo "  App Home (?shop=&host=) unchanged — adfeed-web not restarted"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
