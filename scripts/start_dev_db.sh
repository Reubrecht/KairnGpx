#!/bin/bash


# Ensure we are in the project root
cd "$(dirname "$0")/.."

# Start the PostGIS database
echo "Starting PostGIS database..."
docker compose -f docker-compose.dev.yml up -d db

# Wait for it to be ready
echo "Waiting for database to be ready..."
until docker exec kairn_db_dev pg_isready -U kairn; do
  echo "Waiting for PostGIS..."
  sleep 2
done

echo "Database is ready!"
echo "Connection URL: postgresql://kairn:kairn_password@localhost:5432/kairn"

# Initialize the database (Create tables directly)
echo "Initializing database schema..."
export DATABASE_URL="postgresql://kairn:kairn_password@localhost:5432/kairn"
./.venv/bin/python scripts/init_dev_db.py

# Stamp alembic to head so it knows we are up to date
echo "Stamping alembic head..."
./.venv/bin/python -m alembic stamp head

echo "Setup complete. You can now run the app with 'scripts/run_dev_server.sh'"
