#!/usr/bin/env bash
# One-shot: push local secrets + bootstrap/deploy to a fresh Ubuntu VPS.
# Run from your Mac after SSH works:
#   SERVER=8.222.212.89 SSH_USER=root CERTBOT_EMAIL=you@example.com \
#     bash phase0/scripts/prod/configure-and-deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PHASE0="$(cd "$SCRIPT_DIR/../.." && pwd)"
SECRETS="${SCRIPT_DIR}/.secrets"
SERVER="${SERVER:-deltfu.com}"
SSH_USER="${SSH_USER:-root}"
REMOTE_DIR="${REMOTE_DIR:-/opt/adfeed}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"
SSH_TARGET="${SSH_USER}@${SERVER}"

if [[ ! -f "${SECRETS}/phase0.env" || ! -f "${SECRETS}/web.env" ]]; then
  echo "Missing ${SECRETS}/phase0.env or web.env — generate from local .env first."
  exit 1
fi

echo "┌────────────────────────────────────────┐"
echo "│  AdFeed — configure & deploy"
echo "│  ${SSH_TARGET}:${REMOTE_DIR}"
echo "└────────────────────────────────────────┘"

if ! ssh -o BatchMode=yes -o ConnectTimeout=15 "$SSH_TARGET" 'echo ssh-ok' >/dev/null 2>&1; then
  echo "ERROR: cannot SSH to ${SSH_TARGET}."
  echo "Open Aliyun security group port 22 (and 80/443), then re-run."
  exit 1
fi

# 1) Ensure repo + bootstrap (idempotent)
ssh "$SSH_TARGET" bash -s <<ENDSSH
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
export CERTBOT_EMAIL="${CERTBOT_EMAIL}"
export DOMAIN=deltfu.com
export INSTALL_DIR="${REMOTE_DIR}"
if [[ ! -d ${REMOTE_DIR}/.git ]]; then
  apt-get update -qq
  apt-get install -y -qq git curl
  git clone https://github.com/Benson-XuB/adfeed.git ${REMOTE_DIR}
fi
bash ${REMOTE_DIR}/phase0/scripts/prod/bootstrap-server.sh
ENDSSH

# 2) Upload production env (from local secrets)
scp "${SECRETS}/phase0.env" "${SSH_TARGET}:${REMOTE_DIR}/phase0/.env"
scp "${SECRETS}/web.env" "${SSH_TARGET}:${REMOTE_DIR}/phase0/add-feed-ai/web/.env"
ssh "$SSH_TARGET" "chown adfeed:adfeed ${REMOTE_DIR}/phase0/.env ${REMOTE_DIR}/phase0/add-feed-ai/web/.env && chmod 600 ${REMOTE_DIR}/phase0/.env ${REMOTE_DIR}/phase0/add-feed-ai/web/.env"

# 3) Build locally + rsync + restart
export SERVER SSH_USER REMOTE_DIR
bash "${SCRIPT_DIR}/deploy-from-local.sh"

# 4) Health check
echo ""
echo "━━━ Health ━━━"
curl -fsS "https://deltfu.com/api/health" || curl -fsS "http://${SERVER}/api/health" || true
echo ""
echo "Done. Next (on Mac, once): shopify app deploy with prod URLs."
