#!/bin/bash
# Deploy everything to server2 in one shot
# Usage: bash scripts/deploy.sh

set -e

SERVER2_IP="144.91.126.111"
SSH_USER="root"

echo "=== Full EV Battery Platform Deployment ==="

# 1. Deploy main app
echo "[Step 1/4] Deploying main API..."
bash scripts/deploy_server2.sh

# 2. Deploy Hatchet worker
echo "[Step 2/4] Deploying Hatchet worker..."
bash scripts/deploy_hatchet_worker.sh

# 3. Initialize database
echo "[Step 3/4] Initializing database..."
ssh $SSH_USER@$SERVER2_IP 'psql -U postgres -c "\i /opt/ev-battery-platform/scripts/init_database.sql"'

# 4. Start Crawl4AI
echo "[Step 4/4] Starting Crawl4AI..."
bash scripts/start_crawl4ai.sh

echo ""
echo "=== Deployment Complete ==="
echo "API: http://$SERVER2_IP:8090"
echo "Docs: http://$SERVER2_IP:8090/docs"
echo "Hatchet Worker: running as systemd service"
