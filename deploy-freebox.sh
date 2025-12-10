#!/bin/bash

# Arrêter le script en cas d'erreur
set -e

echo "🚀 Début du déploiement sur Freebox..."

# 1. Récupérer les dernières modifications du code
echo "📥 Pull du code..."
git pull

# 1b. Préparer les dossiers de données (Fix Permissions SQLite)
echo "🔧 Configuration des permissions..."
mkdir -p app/data app/uploads
chmod -R 777 app/data app/uploads

# 2. Vérifier si le token est là (sécurité basique)
if [ ! -f .env ]; then
    echo "⚠️  ATTENTION : Fichier .env manquant !"
    echo "Créez-le avec : Please create it with: TUNNEL_TOKEN=votre_token_ici"
    exit 1
fi

# 3. Reconstruire et relancer les conteneurs (Kairn + Tunnel)
echo "🏗️  Build et Redémarrage..."
docker compose -f docker-compose.freebox.yml up -d --build --remove-orphans

echo "✨ Déploiement terminé ! Vérifiez les logs si besoin : docker compose -f docker-compose.freebox.yml logs -f"
