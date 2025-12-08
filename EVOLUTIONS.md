# Propositions d'Évolutions pour Kairn

Ce document détaille les axes d'amélioration identifiés pour la plateforme Kairn, classés par catégorie (Technique, Fonctionnel, DevOps).

## 1. Architecture & Technique

### Traitement Asynchrone des GPX
Actuellement, l'analyse des fichiers GPX et le géocodage se font de manière synchrone lors de l'upload. Cela peut bloquer le serveur si le fichier est volumineux ou si l'API de géocodage est lente.
* **Proposition**: Implémenter une file de tâches (Task Queue) avec **Celery** et **Redis**.
* **Bénéfice**: Meilleure réactivité de l'interface et gestion des échecs (retries).

### Migration Base de Données
SQLite est utilisé actuellement. Pour un déploiement en production et une meilleure gestion des données géospatiales :
* **Proposition**: Migrer vers **PostgreSQL** avec l'extension **PostGIS**.
* **Bénéfice**: Performance sur les requêtes spatiales (ex: trouver les traces dans un rayon de X km) et fiabilité.

### Refactoring du Code
Le fichier `main.py` contient toute la logique de routing et d'authentification.
* **Proposition**: Découper l'application en utilisant `APIRouter` de FastAPI.
  * `app/routers/auth.py`
  * `app/routers/tracks.py`
  * `app/routers/users.py`
* **Bénéfice**: Meilleure maintenabilité et lisibilité du code.

## 2. Fonctionnalités

### Cartographie Interactive
L'application manque actuellement d'une visualisation dynamique de la trace sur une carte.
* **Proposition**: Intégrer **Leaflet.js** ou **Mapbox** dans la page de détail d'une trace.
* **Fonctionnalités**:
  - Affichage du tracé sur fond de carte (OpenStreetMap, Satellite).
  - Profil altimétrique interactif (au survol du profil, le point se déplace sur la carte).

### Recherche Avancée & Géographique
La recherche actuelle est limitée.
* **Proposition**: Ajouter des filtres avancés :
  - Distance (min/max).
  - Dénivelé (min/max).
  - Recherche géographique (autour d'une ville ou par carte).

### Fonctionnalités Sociales
* **Proposition**:
  - Profils utilisateurs publics.
  - Système de "J'aime" ou de favoris sur les traces.
  - Commentaires sur les traces.

## 3. DevOps & Qualité

### Sécurité & Configuration
Les secrets (Clé JWT, etc.) sont actuellement "en dur" dans le code.
* **Proposition**: Utiliser des variables d'environnement (`.env`) chargées via `pydantic-settings`.

### Tests Automatisés
Le projet ne dispose pas de tests.
* **Proposition**: Mettre en place **Pytest**.
  - Tests unitaires pour `analytics.py` (calculs de distance, dénivelé).
  - Tests d'intégration pour l'API (upload, auth).

### CI/CD
* **Proposition**: Configurer un workflow **GitHub Actions** pour lancer les tests et le linter (flake8/black) à chaque push.
