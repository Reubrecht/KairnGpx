#!/bin/bash

# Configuration
STACK_FILE="docker-compose.freebox.yml"
DATA_DIR="app/data"

echo "======================================"
echo "    Kairn Freebox Deployment Script   "
echo "======================================"
echo ""

# 1. Verification of environment
if [ ! -f "$STACK_FILE" ]; then
    echo "Error: $STACK_FILE not found in current directory."
    exit 1
fi

# 2. Stop current stack
echo ">> Stopping current services..."
docker compose -f $STACK_FILE down

# 3. Pull latest changes
echo ">> Pulling latest code..."
# Stash any local changes on the VM (config tweaks, etc.) to ensure clean pull
git stash
git pull

# 4. Permissions check
echo ">> Checking data permissions..."
# Ensure data dir exists
mkdir -p $DATA_DIR
# Try to set ownership (might require sudo password if user is not root/sudoer without pass)
# Using sudo only if needed or warn user
if [ -w "$DATA_DIR" ]; then
    echo "Data directory is writable."
else
    echo "Warning: Data directory might not be writable. Attempting fix..."
    sudo chown -R 1000:1000 $DATA_DIR
fi

# 5. Start new stack
echo ">> Building and Starting services (Postgres + Kairn)..."
docker compose -f $STACK_FILE up -d --build

# 6. Check health
echo ">> Waiting for services to stabilize..."
sleep 5
docker compose -f $STACK_FILE ps

echo ""
echo "======================================"
echo "    Deployment Complete!             "
echo "======================================"
echo "Logs:"
echo "docker compose -f $STACK_FILE logs -f"
