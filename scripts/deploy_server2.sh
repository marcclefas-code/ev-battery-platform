#!/bin/bash
# Deploy EV Battery Platform to Server2 (144.91.126.111)
# Usage: bash scripts/deploy_server2.sh

set -e

SERVER2_IP="144.91.126.111"
SSH_USER="root"
APP_DIR="/opt/ev-battery-platform"
REPO_URL="https://github.com/marcclefas-code/ev-battery-platform.git"

echo "=== EV Battery Platform Deployment to Server2 ==="

ssh $SSH_USER@$SERVER2_IP << 'REMOTE_COMMANDS'
set -e

echo "[1/7] Creating app directory..."
mkdir -p /opt/ev-battery-platform
cd /opt/ev-battery-platform

echo "[2/7] Cloning / updating repo..."
if [ -d .git ]; then
    git pull origin main
else
    git clone https://github.com/marcclefas-code/ev-battery-platform.git .
fi

echo "[3/7] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/7] Running database migrations..."
# Set environment variables
export DATABASE_URL="${DATABASE_URL:-postgresql+asyncpg://ev_battery_user:ev_battery_pass@localhost:5432/ev_battery}"
export SECRET_KEY="${SECRET_KEY:-change-me-in-production}"
alembic upgrade head
python scripts/seed_property_definitions.py

echo "[5/7] Building Docker image..."
docker build -t ev-battery-platform:latest /opt/ev-battery-platform

echo "[6/7] Stopping existing container..."
docker stop ev-battery-api 2>/dev/null || true
docker rm ev-battery-api 2>/dev/null || true

echo "[7/7] Starting new container..."
docker run -d \
  --name ev-battery-api \
  --restart unless-stopped \
  -p 8090:8090 \
  -e DATABASE_URL="${DATABASE_URL}" \
  -e HATCHET_CLIENT_TOKEN="${HATCHET_CLIENT_TOKEN}" \
  -e HATCHET_CLIENT_HOST_PORT="${HATCHET_CLIENT_HOST_PORT}" \
  -e LITELLM_BASE_URL="${LITELLM_BASE_URL}" \
  -e CRAWL4AI_URL="${CRAWL4AI_URL}" \
  -e REDIS_URL="${REDIS_URL}" \
  -e SECRET_KEY="${SECRET_KEY}" \
  --network=hatchet-network \
  ev-battery-platform:latest

echo "=== Deployment Complete ==="
docker logs ev-battery-api | tail -20
REMOTE_COMMANDS

echo "Deployment script finished. Check server2 logs with: ssh $SSH_USER@$SERVER2_IP 'docker logs ev-battery-api -f'"
