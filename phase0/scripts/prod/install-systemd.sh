#!/usr/bin/env bash
# Install / refresh AdFeed systemd units. Run as root on the server.

set -euo pipefail

INSTALL_DIR="${INSTALL_DIR:-/opt/adfeed}"
PHASE0="${INSTALL_DIR}/phase0"

if [[ "${EUID:-$(id -u)}" -ne 0 ]]; then
  echo "Run as root: sudo $0"
  exit 1
fi

cp "${PHASE0}/adfeed-api.service" /etc/systemd/system/adfeed-api.service
cp "${PHASE0}/adfeed-web.service" /etc/systemd/system/adfeed-web.service

install -d -m 755 /var/log
touch /var/log/adfeed-api.log /var/log/adfeed-web.log
chmod 644 /var/log/adfeed-api.log /var/log/adfeed-web.log

systemctl daemon-reload
systemctl enable adfeed-api adfeed-web

echo "systemd units installed. Start with:"
echo "  systemctl start adfeed-api adfeed-web"
