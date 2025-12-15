# 🏔️ Kairn

[![License](https://img.shields.io/github/license/Reubrecht/Kairn?style=for-the-badge&color=blue)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-3.4-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Google Gemini](https://img.shields.io/badge/AI-Gemini_2.0-8E75B2?style=for-the-badge&logo=google&logoColor=white)

<div align="center">
  <p><strong>The ultimate platform for trail running, community tracking, and AI-powered route analysis.</strong></p>
  
  <a href="#english">🇬🇧 English</a> • <a href="#français">🇫🇷 Français</a>
</div>

---

<a name="english"></a>
## 🇬🇧 English

**Kairn** is an advanced web platform designed for outdoor enthusiasts, specifically tailored for **Trail Running**, **Hiking**, and **Mountain Sports**. It goes beyond traditional GPX viewers by integrating **Artificial Intelligence** to analyze terrain, infer technical difficulty, and provide rich, automated descriptions of your adventures.

### ✨ Key Features

#### 🧠 AI-Powered Analysis
*   **Smart Inference**: Automatically detects track characteristics (e.g., "High Mountain", "Technical", "Forest") using **Google Gemini 2.0**.
*   **Auto-Tagging**: Generates relevant tags and titles based on the GPX geometry and elevation profile.
*   **Rich Descriptions**: Creates engaging descriptions for tracks that lack context.

#### 🌍 Explore & Discover
*   **Proximity Sorting**: Instantly find tracks starting near your location or a specific city.
*   **Hierarchical Event Browser**: Browse official races by Continent > Country > Department > Region > Massif > City.
*   **Advanced Filtering**: Filter by distance, elevation gain (D+), scenery rating, and activity type using intuitive sliders.
*   **Global Heatmap**: Visualize community activity on an interactive 3D map.

#### 🏃‍♂️ Race Management
*   **Official Events**: Structured database of races (Events > Editions > Routes).
*   **Performance Prediction**: Estimate your finish time using our custom algorithm based on your **ITRA Index** and track technicality.
*   **Interactive Maps**: View race routes with detailed overlays, gradients, and waypoints.

#### 👤 Community & Social
*   **User Profiles**: Track your upload history, total stats, and preferred activities.
*   **Role-Based Access**: Granular permissions (User, Moderator, Admin, Super Admin) for content management.
*   **Profile Customization**: Upload profile pictures and manage personal details.

### 🛠️ Technical Stack

Kairn is built with a modern, performance-oriented stack:

*   **Backend**: 
    *   **Python 3.11** with **FastAPI** for high-performance async APIs.
    *   **SQLAlchemy 2.0** ORM for robust database interactions.
    *   **Pydantic** for rigorous data validation.
*   **Database**: 
    *   **PostgreSQL 16** with **PostGIS** extension for advanced geospatial queries (Production).
    *   **SQLite** supported for lightweight local development.
*   **Frontend**: 
    *   **Server-Side Rendering (SSR)** with **Jinja2** templates.
    *   **TailwindCSS** for a responsive, utility-first design system.
    *   **Vanilla JS** for lightweight interactivity (no heavy framework overhead).
    *   **MapLibre GL JS** / **Leaflet** for vector and raster mapping.
*   **AI Integration**: 
    *   **Google Generative AI SDK** (Gemini Models) for content generation and analysis.
*   **Infrastructure**: 
    *   fully containerized with **Docker** and **Docker Compose**.

### 🚀 Getting Started

#### Prerequisites
*   Docker & Docker Compose
*   Git

#### Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd KairnGpx
    ```

2.  **Environment Setup**
    Create a `.env` file based on the example:
    ```bash
    cp .env.freebox.example .env
    ```
    *Edit `.env` to add your `GEMINI_API_KEY` and database credentials.*

3.  **Run with Docker**
    ```bash
    docker compose up -d --build
    ```

4.  **Access the App**
    Open [http://localhost:8000](http://localhost:8000) in your browser.

---

<a name="français"></a>
## 🇫🇷 Français

**Kairn** est une plateforme web avancée conçue pour les passionnés d'outdoor, spécifiquement taillée pour le **Trail Running**, la **Randonnée** et les **Sports de Montagne**. Elle va au-delà des visionneuses GPX traditionnelles en intégrant l'**Intelligence Artificielle** pour analyser le terrain, déduire la technicité et fournir des descriptions détaillées de vos aventures.

### ✨ Fonctionnalités Clés

#### 🧠 Analyse par IA
*   **Inférence Intelligente**: Détecte automatiquement les caractéristiques du parcours (ex: "Haute Montagne", "Technique", "Forêt") via **Google Gemini 2.0**.
*   **Auto-Tagging**: Génère des tags et titres pertinents basés sur la géométrie et le profil du GPX.
*   **Descriptions Enrichies**: Crée des descriptions engageantes pour les traces qui manquent de contexte.

#### 🌍 Explorer & Découvrir
*   **Tri par Proximité**: Trouvez instantanément les traces commençant près de votre position ou d'une ville spécifique.
*   **Navigation Hiérarchique**: Parcourez les courses officielles par Continent > Pays > Département > Région > Massif > Ville.
*   **Filtrage Avancé**: Filtrez par distance, dénivelé (D+), note de paysage et type d'activité via des curseurs intuitifs.
*   **Heatmap Globale**: Visualisez l'activité de la communauté sur une carte 3D interactive.

#### 🏃‍♂️ Gestion de Courses
*   **Événements Officiels**: Base de données structurée (Événements > Éditions > Parcours).
*   **Prédiction de Performance**: Estimez votre temps d'arrivée grâce à notre algorithme basé sur votre **Cote ITRA** et la technicité de la trace.
*   **Cartes Interactives**: Visualisez les parcours avec superpositions détaillées, gradients de pente et points d'intérêt.

#### 👤 Communauté & Social
*   **Profils Utilisateurs**: Suivez votre historique d'upload, vos statistiques globales et activités préférées.
*   **Rôles & Permissions**: Gestion fine des droits (Utilisateur, Modérateur, Admin, Super Admin).
*   **Personnalisation**: Upload de photo de profil et gestion des détails personnels.

### 🛠️ Stack Technique

Kairn est construit sur une stack moderne axée sur la performance :

*   **Backend**: 
    *   **Python 3.11** avec **FastAPI** pour des APIs asynchrones rapides.
    *   **SQLAlchemy 2.0** comme ORM.
    *   **Pydantic** pour la validation de données.
*   **Base de Données**: 
    *   **PostgreSQL 16** avec l'extension **PostGIS** pour les requêtes géospatiales avancées (Production).
    *   **SQLite** supporté pour le développement local léger.
*   **Frontend**: 
    *   **Rendu Côté Serveur (SSR)** avec templates **Jinja2**.
    *   **TailwindCSS** pour un design system responsive et moderne.
    *   **Vanilla JS** pour une interactivité légère sans framework lourd.
    *   **MapLibre GL JS** / **Leaflet** pour la cartographie vectorielle et raster.
*   **Intégration IA**: 
    *   **Google Generative AI SDK** (Modèles Gemini) pour la génération de contenu.
*   **Infrastructure**: 
    *   Entièrement conteneurisé avec **Docker** et **Docker Compose**.

### 🚀 Démarrage Rapide

#### Prérequis
*   Docker & Docker Compose
*   Git

#### Installation

1.  **Cloner le dépôt**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd KairnGpx
    ```

2.  **Configuration de l'environnement**
    Créez un fichier `.env` basé sur l'exemple :
    ```bash
    cp .env.freebox.example .env
    ```
    *Éditez `.env` pour ajouter votre `GEMINI_API_KEY` et vos identifiants base de données.*

3.  **Lancer avec Docker**
    ```bash
    docker compose up -d --build
    ```

4.  **Accéder à l'application**
    Ouvrez [http://localhost:8000](http://localhost:8000) dans votre navigateur.

---

<div align="center">
  <sub>Made with ❤️ by Reubrecht & Antigravity</sub>
</div>
