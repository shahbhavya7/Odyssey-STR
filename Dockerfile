# ---------------------------------------------------------------------------
# Escalio — one image, two roles.
#
# The FastAPI backend (app/) and the Streamlit UI (ui/) share the same code and
# the same requirements.txt, so we build ONE image and pick the role at runtime
# with the `command:` in docker-compose. This keeps the build cache warm and the
# image count low.
#
#   API : uvicorn app.api:app --host 0.0.0.0 --port 8000
#   UI  : streamlit run ui/app.py --server.port 8501 --server.address 0.0.0.0
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# - PYTHONUNBUFFERED: logs show up immediately (no stuck buffer in containers).
# - PYTHONDONTWRITEBYTECODE: no .pyc clutter in the image layer.
# - PYTHONPATH=/code: lets `import app.*` and `import ui.*` resolve from the root.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/code \
    PIP_NO_CACHE_DIR=1

# Runtime libs only:
#   libpq5 — Postgres client library psycopg needs at runtime.
#   curl   — used by the compose healthchecks to hit /health and /_stcore/health.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Install deps first (their own layer) so code edits don't re-run pip every build.
COPY requirements.txt .
RUN pip install -r requirements.txt

# Then the application code.
COPY . .

# Run as a non-root user — good hygiene, and required by some edge/k8s hosts.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /code
USER appuser

# Documentation only; the actual published port is set by compose per service.
EXPOSE 8000 8501

# Default role is the API. Compose overrides this for the UI service.
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
