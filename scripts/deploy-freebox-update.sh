#!/bin/bash
# Script de Mise à jour pour Freebox (Sans suppression des données)

set -e

echo "🚀 Mise à jour de Kairn (Update Mode)"
echo "======================================"

# 1. Récupérer les changements git
echo "📥 Git Pull..."
git pull

# 2. Redémarrer les conteneurs (Sans effacer les volumes)
echo "🔄 Redémarrage des conteneurs..."
# On arrête les conteneurs pour être sûr
docker compose -f docker-compose.freebox.yml down

# On relance avec build pour intégrer les modifs de code (Python)
docker compose -f docker-compose.freebox.yml up -d --build

echo ""
echo "✅ Mise à jour terminée avec succès !"
echo "📊 Vos données (kairn.db et uploads) sont conservées."
echo "🌍 Accès : http://$(hostname -I | awk '{print $1}'):8000"
