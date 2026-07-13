#!/usr/bin/env bash
# Start the Escalio API.
# Interactive docs (Swagger UI) are then at http://localhost:8000/docs
set -e
uvicorn app.api:app --reload --port 8000
