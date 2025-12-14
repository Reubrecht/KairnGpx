#!/bin/bash
# Kairn Freebox Deployment Script

set -e

echo "🚀 Kairn Freebox Deployment Script"
echo "===================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Fichier .env manquant !"
    echo "📝 Copiez .env.freebox.example vers .env et remplissez les variables"
    echo ""
    echo "  cp .env.freebox.example .env"
    echo "  nano .env"
    echo ""
    exit 1
fi

# Create data directories
echo "📁 Création des dossiers de données..."
mkdir -p app/data
mkdir -p app/uploads
chmod 755 app/data app/uploads

#Build and start containers
echo "🐳 Construction et démarrage des conteneurs..."
docker-compose -f docker-compose.freebox.yml down
docker-compose -f docker-compose.freebox.yml build --no-cache
docker-compose -f docker-compose.freebox.yml up -d

echo ""
echo "✅ Déploiement terminé !"
echo ""
echo "📊 Vérifiez les logs avec :"
echo "   docker-compose -f docker-compose.freebox.yml logs -f"
echo ""
echo "🌐 Accès local : http://$(hostname -I | awk '{print $1}'):8000"
echo ""
