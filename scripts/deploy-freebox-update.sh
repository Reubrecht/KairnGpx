#!/bin/bash
# Script de Mise à jour pour Freebox (Sans suppression des données)

set -e

echo "🚀 Mise à jour de Kairn (Update Mode)"
echo "======================================"

# 1. Récupérer les changements git
# 1. Récupérer les changements git (Force Sync)
echo "📥 Git Fetch & Reset..."
git fetch origin
git reset --hard origin/master

# 2. Redémarrer les conteneurs (Sans effacer les volumes)
echo "🔄 Redémarrage des conteneurs..."
# On arrête les conteneurs pour être sûr
docker compose -f docker-compose.freebox.yml down

# On relance avec build pour intégrer les modifs de code (Python)
docker compose -f docker-compose.freebox.yml up -d --build

# 3. Appliquer les migrations légères (DB Schema Update)
echo "🛠️ Vérification et application des migrations..."
# On attend quelques secondes que la DB soit prête
sleep 5
docker compose -f docker-compose.freebox.yml exec -T kairn python scripts/simple_migration.py

echo ""
echo "✅ Mise à jour terminée avec succès !"
echo "📊 Vos données (kairn.db et uploads) sont conservées."
echo "🌍 Accès : http://$(hostname -I | awk '{print $1}'):8000"
