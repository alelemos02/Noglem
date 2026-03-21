#!/bin/sh
set -e

echo "=== Running database migrations ==="
python -c "
from app.core.config import settings
print(f'DB: {settings.DATABASE_URL[:40]}...')
print(f'DB Sync: {settings.DATABASE_URL_SYNC[:40]}...')
"

# Run alembic with a timeout to prevent hanging
if ! timeout 30 alembic upgrade head 2>&1; then
    echo "ERROR: Alembic migration failed or timed out. Check logs above."
fi

echo "=== Starting Conhecimento RAG API server ==="
exec python run.py
