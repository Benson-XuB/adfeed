#!/usr/bin/env bash
set -euo pipefail

# Server-side deploy wrapper (git pull + restart).
# For full options see phase0/scripts/prod/deploy-on-server.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "${SCRIPT_DIR}/scripts/prod/deploy-on-server.sh" "$@"
