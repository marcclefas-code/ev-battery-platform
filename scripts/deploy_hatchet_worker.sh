#!/bin/bash
# Deploy Hatchet Worker to Server2
# Usage: bash scripts/deploy_hatchet_worker.sh

set -e

SERVER2_IP="144.91.126.111"
SSH_USER="root"
WORKER_DIR="/opt/ev-battery-worker"

echo "=== Deploying Hatchet Worker to Server2 ==="

ssh $SSH_USER@$SERVER2_IP << 'REMOTE_COMMANDS'
set -e

mkdir -p $WORKER_DIR
cd $WORKER_DIR

echo "[1/4] Copying worker code..."
cp -r /opt/ev-battery-platform/app/worker /opt/ev-battery-worker/
cp /opt/ev-battery-platform/requirements.txt /opt/ev-battery-worker/

echo "[2/4] Setting up venv..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
# Install Hatchet SDK
pip install hatchet-sdk

echo "[3/4] Creating worker service..."
cat > /etc/systemd/system/ev-battery-worker.service << EOF
[Unit]
Description=EV Battery Hatchet Worker
After=network.target hatchet-engine.service
Requires=hatchet-engine.service

[Service]
Type=simple
User=root
WorkingDirectory=$WORKER_DIR
Environment="PYTHONPATH=$WORKER_DIR"
Environment="DATABASE_URL=${DATABASE_URL}"
Environment="HATCHET_CLIENT_TOKEN=${HATCHET_CLIENT_TOKEN}"
Environment="HATCHET_CLIENT_HOST_PORT=${HATCHET_CLIENT_HOST_PORT}"
Environment="LITELLM_BASE_URL=${LITELLM_BASE_URL}"
ExecStart=$WORKER_DIR/venv/bin/python -m app.worker.hatchet_worker
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

echo "[4/4] Starting worker service..."
systemctl daemon-reload
systemctl enable ev-battery-worker
systemctl restart ev-battery-worker
systemctl status ev-battery-worker --no-pager

echo "=== Hatchet Worker Deployed ==="
REMOTE_COMMANDS

echo "Worker deployed. Check status: ssh $SSH_USER@$SERVER2_IP 'systemctl status ev-battery-worker'"
