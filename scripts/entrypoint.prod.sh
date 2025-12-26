#!/bin/bash
set -e

# Wait for the database to be ready
echo "⏳ Waiting for database connection..."
python /app/scripts/wait_for_db.py

# Run migrations
echo "🔄 Running database migrations..."
alembic upgrade head

# Start the application
echo "🚀 Starting application..."
exec "$@"
