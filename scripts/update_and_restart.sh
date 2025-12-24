#!/bin/bash
set -e

echo "🚀 Starting KairnGpx Update..."
echo "=============================="

# Navigate to the project directory
# Navigate to the project directory (parent of scripts dir)
cd "$(dirname "$0")/.."

echo "📥 Pulling latest changes..."
git pull

echo "♻️  Recreating Docker containers..."
docker compose -f docker-compose.freebox.yml down
docker compose -f docker-compose.freebox.yml up -d --build

echo "✅ Update and Restart Complete!"
echo "Press Enter to close this window..."
read
