#!/bin/bash

echo "🚀 Starting Deployment..."

# 1. Pull latest code
git pull origin master

# 2. Build and Up (using prod config)
# We use --build to ensure new changes are picked up
# -d for detached mode
docker compose -f docker-compose.prod.yml up -d --build

echo "✅ Deployment Complete! Caddy is handling HTTPS for app.mykairn.fr"
