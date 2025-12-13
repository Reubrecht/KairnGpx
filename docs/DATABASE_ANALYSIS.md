# Analyse de Migration Base de Données : SQLite vs PostgreSQL

## État Actuel (SQLite)
Votre application utilise actuellement **SQLite**.
- **Avantages** : Simple (un seul fichier `kairn.db`), aucune configuration serveur, parfait pour le développement et les petits déploiements mono-utilisateur.
- **Limites** :
    - **Gestion des écritures** : Supporte mal les écritures simultanées (une seule écriture à la fois).
    - **Fonctions limitées** : Pas de types de données avancés natifs (Tableaux, Géométrie optimisée).
    - **Intégrité** : Moins rigoureux sur le typage des données.

## Pourquoi passer à PostgreSQL ?

Pour une application communautaire de Trail/GPX comme **Kairn**, PostgreSQL est le choix standard pour plusieurs raisons critiques :

### 1. 🌍 PostGIS : Le Super-Pouvoir Géographique
C'est l'argument n°1. PostgreSQL possède une extension appelée **PostGIS**.
- **Actuellement** : Pour trouver "les traces à moins de 20km de Chamonix", vous devez probablement charger toutes les traces ou faire des calculs approximatifs coûteux en Python.
- **Avec PostGIS** : Vous pouvez exécuter des requêtes spatiales natives ultra-rapides.
    - *Exemple* : Trouver toutes les traces qui croisent une zone protégée.
    - *Exemple* : "Donne-moi les traces dont le point de départ est dans ce rayon de 10km".
    - Le stockage des coordonnées (Lat/Lon) devient un type `GEOMETRY` indexé.

### 2. ⚡ Performance et Concurrence
SQLite verrouille tout le fichier lors d'une écriture. Si 5 utilisateurs uploadent une trace en même temps :
- **SQLite** : Les requêtes s'attendent les unes les autres, risque d'erreur "Database is locked".
- **PostgreSQL** : Gère des centaines/milliers de connexions simultanées sans problème. C'est indispensable si vous ouvrez l'app à une communauté.

### 3. 🔍 JSONB (Données Flexibles)
Vos modèles `Track` et `User` utilisent beaucoup de champs `JSON` (ex: `technical_rating_context`, `surface_composition`).
- **PostgreSQL** possède le type `JSONB` (JSON Binaire) qui permet **d'indexer** ces données.
- Vous pourrez faire des requêtes comme : *"Trouver toutes les traces où `surface_composition.trail` > 80%"* directement en SQL, instantanément.

### 4. 🛡️ Robustesse des Données
PostgreSQL est strict. Il ne vous laissera pas insérer une chaine de charactères dans un champ date par erreur. Il garantit une meilleure intégrité des données à long terme.

## Les Inconvénients (Coûts de Migration)

1.  **Complexité d'Infrastructure** : Il faut lancer un service (conteneur Docker) supplémentaire. Ce n'est plus juste un fichier.
    - *Solution* : Avec votre `docker-compose`, c'est trivial (juste ajouter un service `db`).
2.  **Migration des Données** : Il faut transférer les données existantes de `kairn.db` vers Postgres. C'est une opération unique mais délicate.
3.  **Backups** : On ne peut plus juste copier le fichier `.db`. Il faut scripter des `pg_dump`.

## 🏁 Recommandation

**Si Kairn a vocation à être multi-utilisateurs et public : PASSEZ À POSTGRESQL.**

Le gain apporté par **PostGIS** pour la gestion des traces GPX et la **gestion de la concurrence** pour les utilisateurs justifie largement la petite complexité ajoutée au `docker-compose`.

### Plan de Migration Suggéré
1.  Ajouter le service `postgres` et `postgis` dans `docker-compose.yml`.
2.  Installer `psycopg2-binary` et `geoalchemy2` (pour PostGIS).
3.  Adapter la configuration de base de données dans `database.py`.
4.  Utiliser un script de migration (ou Alembic) pour recréer les tables.
