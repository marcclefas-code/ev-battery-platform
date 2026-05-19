#!/bin/bash
set -e

echo "Starting FastAPI server..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8090
