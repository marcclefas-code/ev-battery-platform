#!/bin/bash
set -e

echo "Starting Hatchet worker in background..."
python -m app.worker.hatchet_worker &
WORKER_PID=$!

trap "kill $WORKER_PID 2>/dev/null; exit 0" INT TERM

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8090
