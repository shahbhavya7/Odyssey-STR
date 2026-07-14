#!/usr/bin/env bash
# Start the Escalio API and Streamlit UI together.
# API docs:      http://localhost:8000/docs
# Streamlit UI:  http://localhost:8501
set -e

cleanup() {
  echo ""
  echo "Stopping Escalio..."
  kill "$API_PID" "$UI_PID" 2>/dev/null
  wait "$API_PID" "$UI_PID" 2>/dev/null
  exit 0
}
trap cleanup INT TERM

uvicorn app.api:app --reload --port 8000 &
API_PID=$!

streamlit run ui/app.py --server.port 8501 &
UI_PID=$!

echo "API running (pid $API_PID) at http://localhost:8000"
echo "UI running (pid $UI_PID) at http://localhost:8501"
echo "Press Ctrl+C to stop both."

wait "$API_PID" "$UI_PID"
