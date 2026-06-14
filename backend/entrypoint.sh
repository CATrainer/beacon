#!/usr/bin/env bash
set -euo pipefail

# Wait for Postgres to accept connections (compose healthcheck also gates this).
echo "[entrypoint] waiting for database..."
python - <<'PY'
import time, sys
from sqlalchemy import create_engine, text
from app.config import settings

for attempt in range(30):
    try:
        engine = create_engine(settings.database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[entrypoint] database is up.")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] db not ready ({attempt+1}/30): {exc}")
        time.sleep(2)
print("[entrypoint] database never became ready", file=sys.stderr)
sys.exit(1)
PY

echo "[entrypoint] running migrations..."
alembic upgrade head

# Idempotently seed the default Clinics & Travel lanes so the queue/Lanes UI
# isn't empty on first boot. Creating the login user is a one-line manual step
# (see docs/SETUP.md) because it needs a password.
echo "[entrypoint] seeding default lanes (idempotent)..."
python -m app.scripts.seed_lanes || echo "[entrypoint] lane seed skipped/failed (non-fatal)"

# Local-only convenience: seed a default login so you can sign in without a
# manual step. No-op unless APP_ENV=local and DEV_AUTOSEED_* are set.
if [ "${APP_ENV:-local}" = "local" ]; then
  python -m app.scripts.seed_dev_user || echo "[entrypoint] dev autoseed skipped (non-fatal)"
fi

if [ "${APP_RELOAD:-0}" = "1" ]; then
  echo "[entrypoint] starting uvicorn (reload)..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  echo "[entrypoint] starting uvicorn..."
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000
fi
