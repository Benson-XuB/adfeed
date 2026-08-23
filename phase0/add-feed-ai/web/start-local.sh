#!/bin/bash
set -euo pipefail
WEB_DIR="/Users/xubaotian/adfeed-ai/phase0/add-feed-ai/web"
cd "$WEB_DIR"
set -a
# shellcheck disable=SC1091
source "$WEB_DIR/.env"
set +a
exec npm run start --workspace=adfeed-web --prefix /Users/xubaotian/adfeed-ai/phase0/add-feed-ai
