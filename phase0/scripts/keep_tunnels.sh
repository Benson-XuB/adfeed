#!/usr/bin/env bash
# Keep API + web cloudflared tunnels alive (separate metrics ports).
set -uo pipefail
API_LOG=/tmp/adfeed-cf-api.log
WEB_LOG=/tmp/adfeed-cf-web.log

start_api() {
  pkill -f 'cloudflared tunnel --url http://127.0.0.1:8000' 2>/dev/null || true
  : >"$API_LOG"
  nohup cloudflared tunnel \
    --url http://127.0.0.1:8000 \
    --protocol http2 \
    --no-autoupdate \
    --metrics 127.0.0.1:20241 \
    >>"$API_LOG" 2>&1 &
  disown
}

start_web() {
  pkill -f 'cloudflared tunnel --url http://127.0.0.1:3000' 2>/dev/null || true
  : >"$WEB_LOG"
  nohup cloudflared tunnel \
    --url http://127.0.0.1:3000 \
    --protocol http2 \
    --no-autoupdate \
    --metrics 127.0.0.1:20243 \
    >>"$WEB_LOG" 2>&1 &
  disown
}

alive() {
  pgrep -f "$1" >/dev/null
}

while true; do
  alive 'cloudflared tunnel --url http://127.0.0.1:8000' || start_api
  alive 'cloudflared tunnel --url http://127.0.0.1:3000' || start_web
  sleep 5
done
