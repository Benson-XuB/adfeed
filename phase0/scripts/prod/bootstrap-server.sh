#!/usr/bin/env bash
# AdFeed AI — one-time Ubuntu 24.04 server bootstrap (Aliyun 2C2G+).
#
# Run on a fresh VPS as root:
#   curl -fsSL https://raw.githubusercontent.com/Benson-XuB/adfeed/main/phase0/scripts/prod/bootstrap-server.sh | bash
# Or after cloning:
#   sudo bash phase0/scripts/prod/bootstrap-server.sh
#
# Before running: point deltfu.com DNS A record to this server.

set -euo pipefail

DOMAIN="${DOMAIN:-deltfu.com}"
REPO_URL="${REPO_URL:-https://github.com/Benson-XuB/adfeed.git}"
INSTALL_DIR="${INSTALL_DIR:-/opt/adfeed}"
APP_USER="${APP_USER:-adfeed}"
SWAP_GB="${SWAP_GB:-2}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

echo "┌────────────────────────────────────────┐"
echo "│  AdFeed AI — bootstrap ${DOMAIN}"
echo "└────────────────────────────────────────┘"

export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  git curl ca-certificates nginx certbot python3-certbot-nginx \
  python3 python3-venv python3-pip build-essential \
  ufw rsync

# ── swap (helps npm build / pip on 2GB) ──
if [[ ! -f /swapfile ]]; then
  echo "Creating ${SWAP_GB}G swap..."
  fallocate -l "${SWAP_GB}G" /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=$((SWAP_GB * 1024))
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

# ── app user ──
if ! id "$APP_USER" &>/dev/null; then
  useradd -m -s /bin/bash "$APP_USER"
fi

# ── Node 20 ──
if ! command -v node &>/dev/null || [[ "$(node -v | cut -d. -f1 | tr -d v)" -lt 20 ]]; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  apt-get install -y -qq nodejs
fi
echo "Node $(node -v) / npm $(npm -v)"

# ── clone repo ──
if [[ ! -d "${INSTALL_DIR}/.git" ]]; then
  git clone "$REPO_URL" "$INSTALL_DIR"
else
  echo "Repo already at ${INSTALL_DIR}, pulling..."
  git -C "$INSTALL_DIR" pull origin main || true
fi
chown -R "${APP_USER}:${APP_USER}" "$INSTALL_DIR"

# ── Python venv ──
VENV="${INSTALL_DIR}/.venv"
if [[ ! -d "$VENV" ]]; then
  sudo -u "$APP_USER" python3 -m venv "$VENV"
fi
sudo -u "$APP_USER" "$VENV/bin/pip" install -q --upgrade pip
sudo -u "$APP_USER" "$VENV/bin/pip" install -q -r "${INSTALL_DIR}/phase0/requirements.txt"

# ── runtime dirs ──
install -d -o "$APP_USER" -g "$APP_USER" \
  "${INSTALL_DIR}/phase0/feeds" \
  "${INSTALL_DIR}/phase0/data" \
  "${INSTALL_DIR}/phase0/output"

# ── env templates ──
if [[ ! -f "${INSTALL_DIR}/phase0/.env" ]]; then
  cp "${INSTALL_DIR}/phase0/.env.example" "${INSTALL_DIR}/phase0/.env"
  chown "$APP_USER:$APP_USER" "${INSTALL_DIR}/phase0/.env"
  echo ""
  echo ">>> Edit ${INSTALL_DIR}/phase0/.env (API keys, Shopify secrets)"
fi
if [[ ! -f "${INSTALL_DIR}/phase0/add-feed-ai/web/.env" ]]; then
  cp "${INSTALL_DIR}/phase0/add-feed-ai/web/.env.example" "${INSTALL_DIR}/phase0/add-feed-ai/web/.env"
  chown "$APP_USER:$APP_USER" "${INSTALL_DIR}/phase0/add-feed-ai/web/.env"
  echo ">>> Edit ${INSTALL_DIR}/phase0/add-feed-ai/web/.env"
fi

# ── nginx ──
cp "${INSTALL_DIR}/nginx/deltfu.com.conf" "/etc/nginx/sites-available/${DOMAIN}"
ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
rm -f /etc/nginx/sites-enabled/default
cp "${INSTALL_DIR}/nginx/deltfu-feeds.conf" /etc/nginx/conf.d/deltfu-feeds.conf
nginx -t

# ── TLS (needs DNS) ──
if [[ -n "$CERTBOT_EMAIL" ]]; then
  certbot --nginx -d "$DOMAIN" -d "www.${DOMAIN}" \
    --non-interactive --agree-tos -m "$CERTBOT_EMAIL" --redirect || true
else
  echo "Skip certbot (set CERTBOT_EMAIL=you@example.com to auto-issue TLS)."
fi

# ── firewall ──
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable || true

# ── systemd ──
bash "${INSTALL_DIR}/phase0/scripts/prod/install-systemd.sh"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Bootstrap done."
echo "  1. Fill in ${INSTALL_DIR}/phase0/.env and web/.env"
echo "  2. Deploy app: bash ${INSTALL_DIR}/phase0/scripts/prod/deploy-on-server.sh"
echo "     (or from Mac: phase0/deploy-from-local.sh)"
echo "  3. shopify app deploy with shopify.app.toml.prod-backup URLs"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
