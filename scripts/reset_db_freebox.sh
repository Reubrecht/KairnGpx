#!/bin/bash
# Script pour réinitialiser la base de données sur la Freebox (Docker)

echo "⚠️  ATTENTION : CELA VA EFFACER TOUTES LES DONNÉES DE LA BASE DE DONNÉES !"
read -p "Êtes-vous sûr de vouloir continuer ? (oui/non) " confirm

if [ "$confirm" != "oui" ]; then
    echo "Annulé."
    exit 1
fi

echo "🔄 Réinitialisation de la base de données..."
docker compose -f docker-compose.freebox.yml exec kairn python reset_db.py

echo "✅ Base de données réinitialisée."
echo "💡 Pensez à recréer votre compte super admin :"
echo "   docker compose -f docker-compose.freebox.yml exec kairn python create_super_admin.py VOTRE_USERNAME"
