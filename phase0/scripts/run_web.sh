#!/usr/bin/env bash
# Keep React Router web alive on :3000 (restart on crash).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)/add-feed-ai/web"
cd "$ROOT"
while true; do
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
  echo "[run_web] starting on :3000 at $(date) BACKEND=$BACKEND_URL" >>/tmp/adfeed-web-local.log
  env \
    VITE_BACKEND_URL="$VITE_BACKEND_URL" \
    BACKEND_URL="$BACKEND_URL" \
    SHOPIFY_API_KEY="$SHOPIFY_API_KEY" \
    SHOPIFY_API_SECRET="$SHOPIFY_API_SECRET" \
    SCOPES="$SCOPES" \
    SHOPIFY_APP_URL="$SHOPIFY_APP_URL" \
    PORT=3000 \
    NODE_ENV=production \
    npm run start >>/tmp/adfeed-web-local.log 2>&1
  echo "[run_web] exited, restart in 2s" >>/tmp/adfeed-web-local.log
  sleep 2
done
