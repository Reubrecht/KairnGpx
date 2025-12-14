#!/bin/bash
# Script de Reset "Force Brute" pour Freebox
# Utile si le script soft n'a pas fonctionné (pb lock sqlite)

echo "🛑 ARRÊT DES CONTENEURS..."
docker compose -f docker-compose.freebox.yml stop kairn

echo "🧨 SUPPRESSION DU FICHIER DB (FORCE)..."
# On utilise une image alpine/python légère pour supprimer le fichier monté dans le volume
# Cela évite les problèmes de permissions root/user sur le host
docker compose -f docker-compose.freebox.yml run --rm kairn rm -f /app/app/data/kairn.db

echo "🔄 REDÉMARRAGE ET RECREATION..."
docker compose -f docker-compose.freebox.yml up -d

echo "✅ Terminé."
echo "⚠️  N'oubliez pas de recréer votre Super Admin :"
echo "   docker compose -f docker-compose.freebox.yml exec kairn python create_super_admin.py VOTRE_USERNAME"
