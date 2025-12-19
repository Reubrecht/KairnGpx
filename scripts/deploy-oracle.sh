#!/bin/bash
# Script de déploiement pour Oracle Cloud

set -e

echo "🚀 Déploiement de Kairn sur Oracle Cloud"
echo "======================================="

# 1. Récupérer les changements git
echo "📥 Git Pull..."
git pull origin master

# 2. Rebuild et redémarrage des conteneurs
echo "🔄 Redémarrage des conteneurs..."
docker compose -f docker-compose.oracle.yml up -d --build

# 3. Appliquer les migrations
echo "🛠️ Application des migrations..."
# Attente que la DB soit prête
sleep 10
docker compose -f docker-compose.oracle.yml exec -T kairn python scripts/simple_migration.py

echo ""
echo "✅ Déploiement terminé !"
echo "🌍 Vérifiez les logs avec : docker compose -f docker-compose.oracle.yml logs -f"
