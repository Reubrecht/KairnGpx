# 🏔️ MyKairn

![License](https://img.shields.io/github/license/jreub/Kairn?style=for-the-badge&color=blue)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Google Gemini](https://img.shields.io/badge/Google_Gemini-8E75B2?style=for-the-badge&logo=google&logoColor=white)

[English](#english) | [Français](#français)

---

<a name="english"></a>
## 🇬🇧 English

**MyKairn** is an advanced, community-driven platform designed for trail runners and outdoor enthusiasts. It goes beyond simple GPX visualization by leveraging **Artificial Intelligence** to analyze terrain, infer technical difficulty, and categorize environments automatically.

Whether you are planning your next ultra-trail, managing a race calendar, or simply sharing a weekend run, MyKairn provides the tools to visualize and understand the path ahead.

### ✨ Key Features

*   **🧠 AI-Powered Analysis**: Utilizes **Google Gemini 2.0** to automatically detect track characteristics (e.g., "High Mountain", "Coastal", "Technical Rocky Terrain") and generate rich descriptions.
*   **🏃‍♂️ Race & Event Management**:
    *   Full support for managing **Races**, **Editions** (yearly iterations), and standard **Routes**.
    *   **Performance Prediction**: Estimate your finish time based on your ITRA index using our custom prediction model.
*   **🗺️ Advanced Mapping**:
    *   Interactive maps with **Leaflet**.
    *   **Global Heatmap** to visualize community activity.
    *   Slope gradients and elevation profiles.
*   **📊 Smart Filtering**: Filter tracks by distance, elevation gain, technicality, or environment using dual-range sliders.
*   **👤 User & Social**:
    *   Personal profiles with statistics and profile pictures.
    *   Secure authentication and role-based access (User, Moderator, Admin).
*   **⚙️ Administration**: Comprehensive Super Admin dashboard for managing users, approving tracks, and tuning global settings.

### 🛠️ Technical Stack

*   **Backend**: Python (FastAPI), Pydantic, SQLAlchemy.
*   **Database**: PostgreSQL (Production), SQLite (Local Development).
*   **Frontend**: Server-Side Rendering with Jinja2, styled utility-first with **TailwindCSS**. Vanilla JavaScript for interactivity.
*   **AI Integration**: Google Generative AI SDK (Gemini 2.0 models).
*   **Geospatial**: `gpxpy`, `geopy`, `GeoAlchemy2` (PostGIS).
*   **Deployment**: Docker & Docker Compose.

### 🚀 Getting Started

#### Prerequisites
*   Docker & Docker Compose installed.

#### Installation
1.  **Clone the repository**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd Kairn
    ```

2.  **Environment Setup**
    Copy `.env.freebox.example` to `.env` and fill in your API keys (Gemini, Database creds, etc.).

3.  **Run with Docker**
    ```bash
    docker-compose up -d --build
    ```

4.  **Access**
    Visit `http://localhost:8000`.

---

<a name="français"></a>
## 🇫🇷 Français

**MyKairn** est une plateforme avancée dédiée à la communauté du trail running. Elle dépasse la simple visualisation de fichiers GPX en utilisant l'**Intelligence Artificielle** pour analyser le terrain, déduire la technicité et catégoriser l'environnement automatiquement.

Que vous planifiiez votre prochain ultra-trail, gériez un calendrier de courses ou partagiez simplement votre sortie du week-end, MyKairn vous offre les outils pour visualiser et comprendre le chemin à parcourir.

### ✨ Fonctionnalités Clés

*   **🧠 Analyse par IA**: Utilise **Google Gemini 2.0** pour détecter automatiquement les caractéristiques d'un parcours (ex: "Haute Montagne", "Côtier", "Terrain Technique/Rocailleux") et générer des descriptions détaillées.
*   **🏃‍♂️ Gestion de Courses**:
    *   Support complet pour les **Événements**, **Éditions** (itérations annuelles) et **Parcours** standards.
    *   **Prédiction de Performance**: Estimez votre temps d'arrivée basé sur votre cote ITRA grâce à notre modèle prédictif personnalisé.
*   **🗺️ Cartographie Avancée**:
    *   Cartes interactives fluides avec **Leaflet**.
    *   **Heatmap Globale** pour visualiser l'activité de la communauté.
    *   Profils d'élévation et gradients de pente.
*   **📊 Filtrage Intelligent**: Filtrez les parcours par distance, dénivelé, technicité ou environnement via des curseurs double plage.
*   **👤 Social & Profils**:
    *   Profils utilisateurs avec statistiques et photos.
    *   Authentification sécurisée et gestion des rôles (Utilisateur, Modérateur, Admin).
*   **⚙️ Administration**: Tableau de bord Super Admin pour gérer les utilisateurs, valider les traces et ajuster les paramètres globaux.

### 🛠️ Stack Technique

*   **Backend**: Python (FastAPI), Pydantic, SQLAlchemy.
*   **Base de Données**: PostgreSQL (Production), SQLite (Développement Local).
*   **Frontend**: Rendu côté serveur (SSR) avec Jinja2, style moderne via **TailwindCSS**. JavaScript natif pour l'interactivité.
*   **Intégration IA**: Google Generative AI SDK (Modèles Gemini 2.0).
*   **Géospatial**: `gpxpy`, `geopy`, `GeoAlchemy2` (PostGIS).
*   **Déploiement**: Docker & Docker Compose.

### 🚀 Démarrage Rapide

#### Prérequis
*   Docker & Docker Compose installés.

#### Installation
1.  **Cloner le dépôt**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd Kairn
    ```

2.  **Configuration**
    Copiez `.env.freebox.example` en `.env` et renseignez vos clés API (Gemini, identifiants BDD, etc.).

3.  **Lancer avec Docker**
    ```bash
    docker-compose up -d --build
    ```

4.  **Accès**
    Ouvrez `http://localhost:8000` dans votre navigateur.
