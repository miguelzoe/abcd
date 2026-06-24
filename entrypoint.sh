#!/usr/bin/env sh
set -e

echo "[entrypoint] Starting Willy backend..."

if [ -z "$DATABASE_URL" ]; then
  echo "[entrypoint] ERROR: DATABASE_URL is not set." >&2
  exit 1
fi

if [ "${WAIT_FOR_DB:-1}" = "1" ]; then
  python - <<'PY'
import os
import sys
import time

import psycopg

database_url = os.environ.get('DATABASE_URL')
retries = int(os.environ.get('DB_WAIT_RETRIES', '30'))
delay = float(os.environ.get('DB_WAIT_DELAY', '2'))

for attempt in range(1, retries + 1):
    try:
        with psycopg.connect(database_url, connect_timeout=5):
            print('[entrypoint] Database is ready.')
            break
    except Exception as exc:
        print(f'[entrypoint] Waiting for database ({attempt}/{retries}): {exc}')
        time.sleep(delay)
else:
    print('[entrypoint] Database connection failed after all retries.', file=sys.stderr)
    sys.exit(1)
PY
fi

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "[entrypoint] Applying migrations..."
  python manage.py migrate --noinput
fi

if [ "${COLLECT_STATIC:-1}" = "1" ]; then
  echo "[entrypoint] Collecting static files..."
  python manage.py collectstatic --noinput
fi

echo "[entrypoint] Launch command: $*"
exec "$@"
