# Escalio

Escalio routes customer-support messages into a category, priority, assigned team,
and reasoning. It stores every routed ticket in PostgreSQL and exposes both a
FastAPI service and a Streamlit UI.

## Local development

1. Copy the example configuration and set the provider values you need:

   ```bash
   cp .env.example .env
   ```

2. Start local PostgreSQL and Ollama (or configure OpenAI in `.env`).

3. Install dependencies and run the app:

   ```bash
   pip install -r requirements.txt
   uvicorn app.api:app --reload --port 8000
   ```

   In another terminal:

   ```bash
   streamlit run ui/app.py
   ```

The API creates the `tickets` table automatically at startup. Open
`http://localhost:8000/docs` for the interactive API documentation.

## Using Neon (serverless Postgres)

1. Sign up at [Neon](https://neon.tech), create a project, and copy its **psycopg**
   connection string.
2. In `.env`, set `DATABASE_URL` to that connection string. Change the scheme from
   `postgresql://` to `postgresql+psycopg://`, use the Neon `-pooler` host, and
   ensure the URL ends with `?sslmode=require`:

   ```dotenv
   DATABASE_URL=postgresql+psycopg://USER:PASSWORD@ENDPOINT-pooler.REGION.aws.neon.tech/DBNAME?sslmode=require
   ```

3. Run the API and UI exactly as above. `init_db()` creates the `tickets` table on
   the hosted database automatically; no model, query, or source change is needed.

Neon's free tier can auto-suspend after idle time. The first request after idle may take
about 1–2 seconds while the database wakes, and `/health` can briefly reflect that
wake delay. This is expected; subsequent requests are fast. Connection pooling uses
`pool_pre_ping` so stale connections are replaced automatically.

Security: a Neon connection URL contains a password. Keep it only in `.env`, which is
already gitignored—never put it in code or commit it.
