# Kairn - Déploiement Freebox Delta

Ce guide explique comment déployer Kairn sur votre Freebox Delta avec Docker et Cloudflare Tunnel.

## Prérequis

- Freebox Delta avec VM activée
- Docker et Docker Compose installés sur la VM
- Compte Cloudflare avec un tunnel configuré
- Clé API Gemini (https://aistudio.google.com/apikey)

## Installation

### 1. Cloner le projet sur la VM Freebox

```bash
git clone https://github.com/Reubrecht/KairnGpx.git
cd KairnGpx
```

### 2. Créer le fichier .env

```bash
cp .env.freebox.example .env
nano .env
```

Remplissez les variables :
```env
INVITATION_CODE=votre_code_beta
GEMINI_API_KEY=votre_cle_gemini
TUNNEL_TOKEN=votre_token_cloudflare
```

### 3. Créer les dossiers de données

```bash
mkdir -p app/data
mkdir -p app/uploads
chmod 755 app/data app/uploads
```

### 4. Démarrer l'application

```bash
docker-compose -f docker-compose.freebox.yml up -d
```

### 5. Vérifier les logs

```bash
docker-compose -f docker-compose.freebox.yml logs -f
```

## Accès

- **Local** : `http://<IP_VM_FREEBOX>:8000`
- **Public** : via votre tunnel Cloudflare (ex: `https://app.mykairn.fr`)

## Mise à jour

```bash
git pull
docker-compose -f docker-compose.freebox.yml down
docker-compose -f docker-compose.freebox.yml build --no-cache
docker-compose -f docker-compose.freebox.yml up -d
```

## Arrêt

```bash
docker-compose -f docker-compose.freebox.yml down
```

## Sauvegarde

Les données sont stockées dans :
- `./app/data/kairn.db` - Base de données
- `./app/uploads/` - Fichiers GPX uploadés

Sauvegardez régulièrement ces dossiers !

## Dépannage

### Erreur de permissions
```bash
sudo chown -R 1000:1000 app/data app/uploads
```

### Logs du conteneur
```bash
docker logs kairn
docker logs cloudflared
```

### Redémarrer les conteneurs
```bash
docker compose -f docker-compose.freebox.yml restart
```

## 💥 Reset Complet (Repartir de Zéro)

⚠️ **ATTENTION : Cette action effacera TOUTES les données (utilisateurs, traces, images) !**

```bash
# 1. Arrêter les conteneurs et supprimer les volumes
docker compose -f docker-compose.freebox.yml down -v

# 2. Supprimer les fichiers de données
sudo rm -rf app/data app/uploads

# 3. Recréer les dossiers propres
mkdir -p app/data app/uploads
sudo chown -R 1000:1000 app/data app/uploads 2>/dev/null || chmod 777 app/data app/uploads

# 4. Redémarrer
docker compose -f docker-compose.freebox.yml up -d --build
```


## Sécurité

⚠️ **IMPORTANT** : Ne commitez **JAMAIS** le fichier `.env` sur Git !

Les fichiers `.env`, `local.env`, et `*.db` sont déjà dans `.gitignore`.
