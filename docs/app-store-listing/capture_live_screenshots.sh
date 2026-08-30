#!/usr/bin/env bash
# Capture 1600×900 listing screenshots from the live embedded App Home in Chrome.
# Prereq: local web :3000 + web tunnel deployed (shopify app deploy), logged into Shopify Admin.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SHOTS="$ROOT/screenshots"
STORE="${STORE:-qx2kd5-s7}"
CLIENT_ID="${CLIENT_ID:-ac2bf432a87c7e12cb7c439556fe762b}"
APP_URL="https://admin.shopify.com/store/${STORE}/apps/adfeed-ai"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome not found at $CHROME" >&2
  exit 1
fi

mkdir -p "$SHOTS"

echo "Open AdFeed AI in Chrome (1600×900). Log into Shopify Admin if prompted."
echo "App URL: $APP_URL"
echo

"$CHROME" \
  --new-window \
  --window-size=1600,900 \
  --window-position=0,0 \
  "$APP_URL" >/dev/null 2>&1 &

sleep 2

capture() {
  local name="$1"
  local hint="$2"
  local out="$SHOTS/$name"
  echo "────────────────────────────────────────"
  echo "$hint"
  echo "Frame the App Home (hide extra Admin chrome if you can), then press Enter."
  read -r _
  screencapture -x "$out"
  sips -z 900 1600 "$out" --out "$out" >/dev/null
  echo "wrote $out ($(sips -g pixelWidth -g pixelHeight "$out" 2>/dev/null | awk '/pixel/{print $2}' | paste -sd'x -))"
}

capture "01-confirm-brand.png" "Shot 1/5 — Home: Ad brand + Google only (no Meta/TikTok) + Generate feed"
capture "02-product-list.png" "Shot 2/5 — Product list with photos + Edit this in Shopify"
capture "03-fix-size.png" "Shot 3/5 — Row with Missing size/color + Fix & generate"
capture "04-copy-url.png" "Shot 4/5 — Sidebar feed URL + Copy button"
capture "05-ad-image.png" "Shot 5/5 — Feed drawer: pick ad image for a SKU"

echo
echo "Done. Optional — build screencast from these real UI shots:"
echo "  $ROOT/build_screencast_from_live.sh"
echo "Then: python3 $ROOT/self_test.py"
