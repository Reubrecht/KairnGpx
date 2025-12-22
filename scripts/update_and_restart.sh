#!/bin/bash
set -e

echo "🚀 Starting KairnGpx Update..."
echo "=============================="

# Navigate to the project directory
cd /projet_dev_ssd/KairnGpx

echo "📥 Pulling latest changes..."
git pull

echo "♻️  Recreating Docker containers (Freebox Config)..."
# Stop standard containers if running
docker compose down --remove-orphans 2>/dev/null || true
# Start Freebox containers
docker compose -f docker-compose.freebox.yml down
docker compose -f docker-compose.freebox.yml up -d --build

echo "✅ Update and Restart Complete!"
echo "Press Enter to close this window..."
read
