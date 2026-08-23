#!/usr/bin/env bash
# Render 1600x900 listing screenshots + English-captioned screencast.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SCENES="$ROOT/scenes"
SHOTS="$ROOT/screenshots"
CAST="$ROOT/screencast"
CHROME="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"

if [[ ! -x "$CHROME" ]]; then
  echo "Google Chrome not found at $CHROME" >&2
  exit 1
fi

mkdir -p "$SHOTS" "$CAST" "$SCENES/video"
python3 "$ROOT/build_video_html.py"

shot() {
  local html_path="$1"
  local out="$2"
  local tmp
  tmp="$(mktemp -t adfeed-shot)"
  tmp_png="${tmp}.png"
  "$CHROME" \
    --headless=new \
    --disable-gpu \
    --no-sandbox \
    --disable-web-security \
    --allow-file-access-from-files \
    --hide-scrollbars \
    --force-device-scale-factor=1 \
    --window-size=1600,900 \
    --screenshot="$tmp_png" \
    --virtual-time-budget=5000 \
    "file://${html_path}" >/dev/null 2>&1
  sips -z 900 1600 "$tmp_png" --out "$out" >/dev/null
  rm -f "$tmp" "$tmp_png"
  echo "wrote $out"
}

shot "$SCENES/01-confirm-brand.html" "$SHOTS/01-confirm-brand.png"
shot "$SCENES/02-product-list.html" "$SHOTS/02-product-list.png"
shot "$SCENES/03-fix-size.html" "$SHOTS/03-fix-size.png"
shot "$SCENES/04-copy-url.html" "$SHOTS/04-copy-url.png"
shot "$SCENES/05-ad-image.html" "$SHOTS/05-ad-image.png"
shot "$SCENES/06-change-plan.html" "$SHOTS/06-change-plan.png"

VID="$CAST/frames"
mkdir -p "$VID"
shot "$SCENES/video/01-confirm-brand.html" "$VID/01.png"
shot "$SCENES/video/02-product-list.html" "$VID/02.png"
shot "$SCENES/video/03-fix-size.html" "$VID/03.png"
shot "$SCENES/video/04-copy-url.html" "$VID/04.png"
shot "$SCENES/video/05-ad-image.html" "$VID/05.png"
shot "$SCENES/video/06-change-plan.html" "$VID/06.png"

FFMPEG="$(command -v ffmpeg || true)"
if [[ -z "$FFMPEG" && -x /opt/homebrew/bin/ffmpeg ]]; then
  FFMPEG=/opt/homebrew/bin/ffmpeg
fi
if [[ -z "$FFMPEG" ]]; then
  echo "ffmpeg not on PATH yet; frames are ready in $VID" >&2
  exit 0
fi

LIST="$CAST/concat.txt"
: > "$LIST"
for i in 01 02 03 04 05 06; do
  printf "file '%s'\nduration 13\n" "$VID/${i}.png" >> "$LIST"
done
printf "file '%s'\n" "$VID/06.png" >> "$LIST"

"$FFMPEG" -y -f concat -safe 0 -i "$LIST" \
  -vf "fps=30,format=yuv420p" \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
  "$CAST/adfeed-ai-screencast.mp4"

echo "wrote $CAST/adfeed-ai-screencast.mp4"
