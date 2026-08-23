#!/usr/bin/env bash
# Local iframe test stack for Basic stores (no shopify app dev).
# Starts: FastAPI :8000 + API tunnel + React Router :3000 + web tunnel
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pkill -f 'cloudflared tunnel --url http://127.0.0.1:8000' 2>/dev/null || true
pkill -f 'cloudflared tunnel --url http://127.0.0.1:3000' 2>/dev/null || true
pkill -f 'react-router-serve' 2>/dev/null || true
pkill -f 'scripts/run_web.sh' 2>/dev/null || true
pkill -f 'python server.py' 2>/dev/null || true
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
lsof -tiTCP:3000 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
sleep 1

grep -q '^ADFEED_BILLING_TEST=' .env 2>/dev/null \
  && sed -i '' 's/^ADFEED_BILLING_TEST=.*/ADFEED_BILLING_TEST=true/' .env \
  || echo 'ADFEED_BILLING_TEST=true' >> .env

wait_http() {
  local url="$1" label="$2" tries="${3:-30}"
  for i in $(seq 1 "$tries"); do
    if curl -sf -m 10 "$url" >/dev/null 2>&1; then
      return 0
    fi
    printf '.' >&2
    sleep 1
  done
  echo >&2
  echo "ERROR: $label not ready: $url" >&2
  return 1
}

wait_tun() {
  local log="$1" url=""
  for _ in $(seq 1 60); do
    url=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$log" 2>/dev/null | tail -1 || true)
    [[ -n "$url" ]] && { echo "$url"; return 0; }
    sleep 0.5
  done
  return 1
}

echo "Starting API on :8000..."
nohup env ADFEED_BILLING_TEST=true .venv/bin/python server.py >>/tmp/adfeed-api-local.log 2>&1 &
disown
wait_http "http://127.0.0.1:8000/api/health" "local API" 20

echo -n "Starting API tunnel (may take ~90s) "
: >/tmp/adfeed-cf-api.log
nohup cloudflared tunnel --url http://127.0.0.1:8000 --protocol http2 --no-autoupdate --metrics 127.0.0.1:20241 >>/tmp/adfeed-cf-api.log 2>&1 &
disown
API_TUN="$(wait_tun /tmp/adfeed-cf-api.log)"
wait_http "$API_TUN/api/health" "API tunnel" 120
echo " OK"

grep -q '^ADFEED_PUBLIC_URL=' .env 2>/dev/null \
  && sed -i '' "s|^ADFEED_PUBLIC_URL=.*|ADFEED_PUBLIC_URL=$API_TUN|" .env \
  || echo "ADFEED_PUBLIC_URL=$API_TUN" >> .env
pkill -f 'python server.py' 2>/dev/null || true
sleep 1
nohup env ADFEED_BILLING_TEST=true ADFEED_PUBLIC_URL="$API_TUN" .venv/bin/python server.py >>/tmp/adfeed-api-local.log 2>&1 &
disown
wait_http "http://127.0.0.1:8000/api/health" "local API (restart)" 20

echo "Starting web on :3000 (auto-restart)..."
chmod +x "$ROOT/scripts/run_web.sh"
nohup bash "$ROOT/scripts/run_web.sh" >>/tmp/adfeed-web-local.log 2>&1 &
disown
wait_http "http://127.0.0.1:3000/" "local web" 30

echo -n "Starting web tunnel "
: >/tmp/adfeed-cf-web.log
nohup cloudflared tunnel --url http://127.0.0.1:3000 --protocol http2 --no-autoupdate --metrics 127.0.0.1:20243 >>/tmp/adfeed-cf-web.log 2>&1 &
disown
WEB_TUN="$(wait_tun /tmp/adfeed-cf-web.log)"
echo " $WEB_TUN"

python3 - <<PY
from pathlib import Path
import re
api = "$API_TUN".rstrip("/")
web = "$WEB_TUN".rstrip("/")
root = Path("$ROOT")
env = {}
for line in (root/".env").read_text().splitlines():
    if "=" in line and not line.strip().startswith("#"):
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
(root/"add-feed-ai/web/.env").write_text(
    f"VITE_BACKEND_URL={api}\n"
    f"BACKEND_URL={api}\n"
    f"SHOPIFY_API_KEY={env['SHOPIFY_CLIENT_ID']}\n"
    f"SHOPIFY_API_SECRET={env['SHOPIFY_CLIENT_SECRET']}\n"
    f"SCOPES=read_products,write_products,read_legal_policies\n"
    f"SHOPIFY_APP_URL={web}\n"
    f"PORT=3000\n"
    f"NODE_ENV=production\n"
    f"VITE_UI_LOCALE=en\n"
)
(root/"add-feed-ai/.env").write_text(f"VITE_BACKEND_URL={api}\n")
(root/"add-feed-ai/shared/local-backend.js").write_text(
    f'export const LOCAL_BACKEND_URL = "{api}";\n'
)
toml = root/"add-feed-ai/shopify.app.toml"
text = toml.read_text()
text = re.sub(r'^application_url = ".*"', f'application_url = "{web}"', text, flags=re.M)
text = re.sub(
    r'(uri = ")https://[^"]+(/api/webhooks/shopify/[^"]+")',
    rf"\1{api}\2",
    text,
)
text = re.sub(
    r"\[auth\]\s*redirect_urls = \[[^\]]*\]",
    f'[auth]\nredirect_urls = [\n  "{web}/auth/callback",\n  "{api}/api/shopify/callback",\n]',
    text,
    flags=re.S,
)
toml.write_text(text)
PY

echo -n "Waiting for web tunnel "
wait_http "$WEB_TUN/" "web tunnel" 120
echo " OK"

curl -sf -m 15 -o /dev/null -w "api_tun:%{http_code} " "$API_TUN/api/health"
curl -sf -m 15 -o /dev/null -w "web_tun:%{http_code}\n" "$WEB_TUN/"

echo
echo "API_TUN=$API_TUN"
echo "WEB_TUN=$WEB_TUN"
echo "Next: cd $ROOT/add-feed-ai && shopify app deploy --allow-updates --version adfeed-iframe-local --message \"local iframe test\""
echo "Then: Shopify Admin → Apps → close & re-open AdFeed AI"
