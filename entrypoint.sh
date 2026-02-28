#!/bin/bash
set -e

export PYTHONPATH="/app${PYTHONPATH:+:$PYTHONPATH}"

echo "[entrypoint] Starting Quantum DNS Shield..."

# Start FastAPI backend
echo "[entrypoint] Starting FastAPI on :8000"
uvicorn src.api.app:create_app --factory --host 0.0.0.0 --port 8000 &

# Start Streamlit dashboard
echo "[entrypoint] Starting Streamlit on :8501"
streamlit run src/dashboard/app.py \
    --server.port 8501 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --browser.gatherUsageStats false
