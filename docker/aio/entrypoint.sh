#!/usr/bin/env bash
# One-time Postgres bootstrap, then start all three processes under supervisord.
# Safe to run every boot: the init block only runs when the data dir is empty,
# so a mounted volume keeps your tickets between runs.
set -euo pipefail

PGDATA="${PGDATA:-/var/lib/postgresql/data}"

# A mounted volume can come up owned by root — make sure postgres owns its dir.
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

# First boot only: create the database cluster and the app database.
if [ ! -s "$PGDATA/PG_VERSION" ]; then
  echo "[entrypoint] Initializing PostgreSQL data directory..."
  su postgres -c "initdb -D '$PGDATA' --auth-local=trust --auth-host=trust"

  echo "[entrypoint] Creating the ticketrouter database..."
  su postgres -c "pg_ctl -D '$PGDATA' -o '-c listen_addresses=127.0.0.1' -w start"
  su postgres -c "psql -v ON_ERROR_STOP=1 --username postgres --dbname postgres <<-SQL
      ALTER USER postgres PASSWORD 'postgres';
      CREATE DATABASE ticketrouter;
SQL"
  su postgres -c "pg_ctl -D '$PGDATA' -m fast -w stop"
  echo "[entrypoint] Database ready."
fi

echo "[entrypoint] Starting Postgres + API + UI..."
exec supervisord -c /etc/supervisor/conf.d/escalio.conf
