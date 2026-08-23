#!/usr/bin/env bash
# One-shot: local iframe stack + build + shopify app deploy (Basic plan stores).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "━━━ [1/3] Start API + Web + Cloudflare tunnels ━━━"
bash "$ROOT/scripts/local_iframe_stack.sh"

API_TUN=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/adfeed-cf-api.log 2>/dev/null | tail -1)
WEB_TUN=$(grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com' /tmp/adfeed-cf-web.log 2>/dev/null | tail -1)

echo
echo "━━━ [2/3] Build React Router web ━━━"
cd "$ROOT/add-feed-ai/web"
npm run build

echo
echo "━━━ [3/3] Deploy app config to Shopify ━━━"
cd "$ROOT/add-feed-ai"
VER="adfeed-local-$(date +%m%d-%H%M)"
shopify app deploy --allow-updates --version "$VER" --message "local iframe test"

echo
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Ready for Shopify Admin iframe test"
echo "  API: $API_TUN"
echo "  Web: $WEB_TUN"
echo "  Version: $VER"
echo ""
echo "  1. Keep this Mac awake (API/web/tunnels must stay up)"
echo "  2. Shopify Admin → Apps → close AdFeed AI tab"
echo "  3. Re-open AdFeed AI from Apps list (not just F5)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
