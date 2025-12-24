#!/bin/bash


# Ensure we are in the project root
cd "$(dirname "$0")/.."

export DATABASE_URL="postgresql://kairn:kairn_password@localhost:5432/kairn"

# Load other environment variables if needed from a .env file, but prioritize the DATABASE_URL
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi
# Force the dev DB URL again just in case .env overwrote it
export DATABASE_URL="postgresql://kairn:kairn_password@localhost:5432/kairn"

echo "Starting Kairn Dev Server with PostGIS..."
./.venv/bin/uvicorn app.main:app --reload --port 8000
