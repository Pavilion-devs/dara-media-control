#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update
apt-get install -y --no-install-recommends ca-certificates python3-pip python3-venv

if ! id dara >/dev/null 2>&1; then
  useradd --system --home-dir /opt/dara --shell /usr/sbin/nologin dara
fi

python3 -m venv /opt/dara/venv
/opt/dara/venv/bin/pip install --upgrade pip
/opt/dara/venv/bin/pip install -e /opt/dara/api

chown -R dara:dara /opt/dara
chmod 600 /etc/dara-api.env
install -m 0644 /opt/dara/deploy/dara-api.service /etc/systemd/system/dara-api.service

systemctl daemon-reload
systemctl enable --now dara-api.service
systemctl --no-pager --full status dara-api.service
