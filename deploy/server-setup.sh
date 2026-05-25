#!/bin/bash
# UGC Machine — server setup per Deployment Guide (Ubuntu 24.04).
# Run on the VPS after uploading ugc-machine/ (replace /home/user with your path).

set -e
APP_DIR="${1:-/home/user/ugc-machine}"
DOMAIN="${2:-ugc.yourdomain.com}"
LINUX_USER="${3:-user}"

echo "==> Step 2: install Python + FFmpeg"
sudo apt update
sudo apt install -y python3 ffmpeg nginx certbot python3-certbot-nginx apache2-utils

echo "==> Step 6: systemd service"
sudo sed "s|/home/user/ugc-machine|${APP_DIR}|g; s|^User=user|User=${LINUX_USER}|" \
  "$(dirname "$0")/ugc.service" | sudo tee /etc/systemd/system/ugc.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable ugc
sudo systemctl restart ugc

echo "==> Step 7: Nginx reverse proxy"
sudo sed "s|ugc.yourdomain.com|${DOMAIN}|g" "$(dirname "$0")/nginx-ugc.conf" \
  | sudo tee /etc/nginx/sites-available/ugc > /dev/null
sudo ln -sf /etc/nginx/sites-available/ugc /etc/nginx/sites-enabled/ugc
sudo nginx -t && sudo systemctl reload nginx

echo "==> HTTPS (after DNS points ${DOMAIN} to this server):"
echo "    sudo certbot --nginx -d ${DOMAIN}"
echo ""
echo "==> Optional Basic Auth (recommended before going live):"
echo "    sudo htpasswd -c /etc/nginx/.htpasswd yourusername"
echo "    Then uncomment the auth_basic lines in /etc/nginx/sites-available/ugc"
echo "    sudo nginx -t && sudo systemctl reload nginx"
echo ""
echo "App should be at http://127.0.0.1:8745 — check: sudo systemctl status ugc"
