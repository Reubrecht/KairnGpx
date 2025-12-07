#!/bin/bash

echo "🚀 Starting Kairn Deployment..."

# 1. Ensure directories exist
echo "📂 Creating data directories..."
mkdir -p app/data app/uploads app/static

# 2. Set permissions (Simple fix for Docker volumes on generic VMs)
echo "🔒 Setting permissions..."
chmod -R 777 app/data app/uploads

# 3. Start Docker Compose
echo "🐳 Building and starting containers..."
sudo docker compose up -d --build

echo "✅ Kairn is deployed!"
echo "   Access it at http://$(hostname -I | awk '{print $1}'):8000"
