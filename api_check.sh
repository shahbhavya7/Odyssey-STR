#!/usr/bin/env bash
# Exercise every endpoint. Start the server first: bash run_api.sh
# Readable JSON via python -m json.tool.
set -e
BASE="http://localhost:8000"
pp() { python -m json.tool; }

echo "### 1. GET /health"
curl -s "$BASE/health" | pp

echo; echo "### 2. POST /tickets (route + save)"
RESP=$(curl -s -X POST "$BASE/tickets" \
  -H "Content-Type: application/json" \
  -d '{"text":"I was charged twice, refund please"}')
echo "$RESP" | pp
NEW_ID=$(echo "$RESP" | python -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo; echo "### 3. GET /tickets/$NEW_ID"
curl -s "$BASE/tickets/$NEW_ID" | pp

echo; echo "### 4. GET /tickets?limit=5"
curl -s "$BASE/tickets?limit=5" | pp

echo; echo "### 5. POST /tickets with empty text (still a valid fallback ticket)"
curl -s -X POST "$BASE/tickets" \
  -H "Content-Type: application/json" \
  -d '{"text":" "}' | pp

echo; echo "### 6. GET /tickets/999999 (clean 404)"
curl -s "$BASE/tickets/999999" | pp
