#!/bin/sh
set -e

echo "=== Running database migrations ==="
python -c "
from app.core.config import settings
print(f'DB: {settings.DATABASE_URL[:40]}...')
print(f'DB Sync: {settings.DATABASE_URL_SYNC[:40]}...')
"

# Run alembic before starting the API. If schema migration fails, the deploy must fail.
timeout 120 alembic upgrade head

echo "=== Starting PATEC API server ==="
exec python run.py
