# 🏔️ Kairn - Plateforme Communautaire de Trail

![License](https://img.shields.io/github/license/jreub/Kairn?style=for-the-badge&color=blue)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

**Kairn** est une application web moderne conçue pour la communauté du trail running. Elle permet de partager, analyser et découvrir des traces GPX avec une précision sémantique inégalée (technicité, environnement, type de terrain).

---

## 🚀 Fonctionnalités Clés

-   **Analyses GPX Avancées** : Calcul automatique de la distance, du dénivelé, et analyse des pentes.
-   **Attributs Sémantiques** : Détection automatique de l'environnement (Haute Montagne, Forêt, etc.) et de la technicité.
-   **Exploration Interactive** : Carte thermique mondiale, filtres par distance, dénivelé et ratios.
-   **Suivi des courses** : Base de données des événements (UTMB, etc.) et liaison avec les traces officielles.
-   **Prédiction de Performance** : Algorithmes prédictifs basés sur le profil du coureur et la technicité du terrain.

---

## 🛠️ Architecture Technique

Le projet repose sur une stack robuste et performante :

-   **Backend** : [FastAPI](https://fastapi.tiangolo.com/) (Python Asynchrone)
-   **Base de Données** : SQLAlchemy (SQLite par défaut, migration PostgreSQL prête)
-   **Frontend** : Jinja2 (SSR) + TailwindCSS + Leaflet.js
-   **Déploiement** : Docker Compose

### Structure des Dossiers

```
Kairn/
├── app/                  # Cœur de l'application
│   ├── main.py           # Point d'entrée et routeurs
│   ├── models.py         # Modèles de données (SQLAlchemy)
│   ├── database.py       # Configuration DB
│   ├── services/         # Logique métier (Analytics, AI, Import)
│   ├── templates/        # Vues HTML (Jinja2)
│   └── static/           # Assets (CSS/JS/Images)
├── scripts/              # Utilitaires d'administration et maintenance
│   ├── reset_db.py       # Réinitialisation de la BDD
│   ├── import_races.py   # Imports de données
│   └── deploy.sh         # Scripts de déploiement
├── docs/                 # Documentation technique (Schémas, etc.)
├── Dockerfile            # Configuration image Docker
└── docker-compose.yml    # Orchestration des services
```

---

## 🐳 Installation & Démarrage (Docker)

La méthode recommandée pour lancer Kairn est d'utiliser Docker.

1.  **Cloner le dépôt**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd Kairn
    ```

2.  **Lancer les conteneurs**
    ```bash
    docker-compose up -d --build
    ```

3.  **Accéder à l'application**
    Ouvrez votre navigateur sur `http://localhost:8090` (ou le port configuré dans le docker-compose).

---

## 🔧 Développement Local

Pour contribuer ou modifier le code sans Docker :

1.  **Environnement Virtuel**
    ```bash
    python -m venv venv
    source venv/bin/activate  # (Windows: venv\Scripts\activate)
    ```

2.  **Dépendances**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Lancer le serveur**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

---

## 📚 Documentation Base de Données

Un schéma idéal pour la transition vers **PostgreSQL** est disponible dans [docs/POSTGRES_SCHEMA.md](docs/POSTGRES_SCHEMA.md).

---

## 🤝 Contribuer

Les contributions sont les bienvenues !
1.  Forkez le projet.
2.  Créez une branche (`git checkout -b feature/NouvelleFeature`).
3.  Commitez vos changements.
4.  Poussez vers la branche.
5.  Ouvrez une Pull Request.

---
*Développé avec ❤️ pour les passionnés de montagne.*
