#!/bin/bash
# Start Crawl4AI service on server2
# Required for the Crawl4AI fetcher

set -e

SERVER2_IP="144.91.126.111"
SSH_USER="root"

echo "=== Starting Crawl4AI on Server2 ==="

ssh $SSH_USER@$SERVER2_IP << 'REMOTE'
set -e

# Check if crawl4ai is installed
if ! command -v crawl4ai &> /dev/null; then
    echo "Installing crawl4ai..."
    pip install crawl4ai
fi

# Run crawl4ai in background
echo "Starting crawl4ai server on port 8000..."
nohup crawl4ai server --port 8000 --headless &

echo "Crawl4AI started. Verify: curl http://localhost:8000/health"
REMOTE
