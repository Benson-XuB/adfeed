#!/usr/bin/env bash
# Local AdFeed stack: API :8000 + Cloudflare quick tunnel + print next steps.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Missing .venv — create it and install requirements first."
  exit 1
fi

pkill -f 'cloudflared tunnel --url http://127.0.0.1:8000' 2>/dev/null || true
lsof -tiTCP:8000 -sTCP:LISTEN | xargs kill -9 2>/dev/null || true
sleep 1

.venv/bin/python server.py &
API_PID=$!
sleep 2
curl -sf http://127.0.0.1:8000/api/health >/dev/null

LOG="$(mktemp)"
cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate >"$LOG" 2>&1 &
CF_PID=$!

TUN=""
for _ in $(seq 1 40); do
  TUN=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' "$LOG" 2>/dev/null | head -1 || true)
  [[ -n "$TUN" ]] && break
  sleep 0.5
done
if [[ -z "$TUN" ]]; then
  echo "Tunnel failed. Log: $LOG"
  kill "$API_PID" "$CF_PID" 2>/dev/null || true
  exit 1
fi

printf 'export const LOCAL_BACKEND_URL = "%s";\n' "$TUN" > "$ROOT/add-feed-ai/shared/local-backend.js"
printf 'VITE_BACKEND_URL=%s\n' "$TUN" > "$ROOT/add-feed-ai/.env"
# React Router iframe App Home (Vite)
cat > "$ROOT/add-feed-ai/web/.env" <<EOF
VITE_BACKEND_URL=$TUN
BACKEND_URL=$TUN
EOF

# Keep FastAPI OAuth redirect in sync for this session (webhooks / legacy callback)
python3 - <<PY
from pathlib import Path
import re
tun = "$TUN".rstrip("/")
p = Path("$ROOT/.env")
text = p.read_text() if p.exists() else ""
uri = f"{tun}/api/shopify/callback"
if re.search(r"^SHOPIFY_REDIRECT_URI=", text, re.M):
    text = re.sub(r"^SHOPIFY_REDIRECT_URI=.*$", f"SHOPIFY_REDIRECT_URI={uri}", text, flags=re.M)
else:
    text = text.rstrip() + f"\nSHOPIFY_REDIRECT_URI={uri}\n"
p.write_text(text)
print(tun)
PY

echo
echo "API PID=$API_PID  cloudflared PID=$CF_PID"
echo "Backend tunnel: $TUN"
echo "Health: $(curl -sf "$TUN/api/health")"
echo
echo "=== Next: iframe App Home (React Router in add-feed-ai/web) ==="
echo "1) Keep this terminal alive (API + tunnel)."
echo "2) Preferred — development store:"
echo "     cd $ROOT/add-feed-ai && shopify app dev -s <dev-store>.myshopify.com"
echo "   CLI tunnels the web/ process and sets application_url to the iframe app."
echo "3) Basic plan stores often cannot use app dev; host/deploy the web Node app"
echo "   separately, keep webhook URIs on this API tunnel ($TUN)."
echo "4) Merchant UI is web/ — NOT FastAPI GET / and NOT _retired/app-home."
echo
echo "Keep this terminal alive. Ctrl+C → kill $API_PID $CF_PID"
wait
