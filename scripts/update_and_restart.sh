#!/bin/bash
set -e

echo "🚀 Starting KairnGpx Update..."
echo "=============================="

# Navigate to the project directory
cd /projet_dev_ssd/KairnGpx

echo "📥 Pulling latest changes..."
git pull

echo "♻️  Recreating Docker containers..."
docker compose down
docker compose up -d --build

echo "✅ Update and Restart Complete!"
echo "Press Enter to close this window..."
read
