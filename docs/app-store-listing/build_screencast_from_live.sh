#!/usr/bin/env bash
# Build listing screencast from LIVE screenshots (real App Home UI).
#
# 1) Capture real UI first:
#      ./capture_live_screenshots.sh
#    (log into Shopify Admin when Chrome opens; press Enter after each screen)
#
# 2) Then run this script:
#      ./build_screencast_from_live.sh
#
# Output: screencast/adfeed-ai-screencast-live.mp4
# Upload that file to YouTube (unlisted) for Feature video + Screencast URL.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
SHOTS="$ROOT/screenshots"
CAST="$ROOT/screencast"
FRAMES="$CAST/frames-live"
OUT="$CAST/adfeed-ai-screencast-live.mp4"
SECONDS_PER_SLIDE="${SECONDS_PER_SLIDE:-10}"

FFMPEG="$(command -v ffmpeg || true)"
if [[ -z "$FFMPEG" && -x /opt/homebrew/bin/ffmpeg ]]; then
  FFMPEG=/opt/homebrew/bin/ffmpeg
fi
if [[ -z "$FFMPEG" ]]; then
  echo "ffmpeg not found. Install: brew install ffmpeg" >&2
  exit 1
fi

need=(
  "$SHOTS/01-confirm-brand.png"
  "$SHOTS/02-product-list.png"
  "$SHOTS/03-fix-size.png"
  "$SHOTS/04-copy-url.png"
  "$SHOTS/05-ad-image.png"
)
for f in "${need[@]}"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing $f — run ./capture_live_screenshots.sh first." >&2
    exit 1
  fi
done

mkdir -p "$FRAMES"
i=1
for f in "${need[@]}"; do
  cp "$f" "$FRAMES/$(printf '%02d.png' "$i")"
  i=$((i + 1))
done

LIST="$CAST/concat-live.txt"
: > "$LIST"
for n in 01 02 03 04 05; do
  printf "file '%s'\nduration %s\n" "$FRAMES/${n}.png" "$SECONDS_PER_SLIDE" >> "$LIST"
done
printf "file '%s'\n" "$FRAMES/05.png" >> "$LIST"

"$FFMPEG" -y -f concat -safe 0 -i "$LIST" \
  -vf "fps=30,format=yuv420p" \
  -c:v libx264 -pix_fmt yuv420p -movflags +faststart \
  "$OUT"

echo "wrote $OUT ($(du -h "$OUT" | awk '{print $1}'))"
echo "Next: upload to YouTube (unlisted), embed URL → Partner listing Video URL"
