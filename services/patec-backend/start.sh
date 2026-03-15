#!/bin/sh
set -e

echo "=== Running database migrations ==="
python -c "
from app.core.config import settings
print(f'DB: {settings.DATABASE_URL[:40]}...')
print(f'DB Sync: {settings.DATABASE_URL_SYNC[:40]}...')
"

# Run alembic with a timeout to prevent hanging
timeout 30 alembic upgrade head || echo "WARNING: Alembic migration failed or timed out, continuing..."

echo "=== Starting PATEC API server ==="
exec python run.py
