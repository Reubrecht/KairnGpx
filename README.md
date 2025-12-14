# 🏔️ Kairn - Intelligent Trail Running Platform

![Status](https://img.shields.io/badge/Status-Beta-orange?style=for-the-badge)
![License](https://img.shields.io/github/license/Reubrecht/Kairn?style=for-the-badge&color=blue)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)

**Kairn** is a next-generation web application designed for the trail running community to share, analyze, and discover GPX tracks. Unlike standard mapping tools, Kairn leverages **Semantic Analysis** and **Artificial Intelligence** to understand the *nature* of a track—distinguishing between a runnable forest path and a technical alpine ridge.

---

## 📸 Screenshots

| Dashboard & Activity | Detailed Analysis |
|:--------------------:|:-----------------:|
| ![Dashboard](docs/screenshots/dashboard.webp) | ![Track Detail](docs/screenshots/track_detail.webp) |

> *Explore the interactive heatmap and analyze your performance on specific terrain types.*

---

## ✨ Key Features

### 🏃‍♂️ Advanced Track Analysis
-   **Automated Metrics**: Precise calculation of distance, elevation gain/loss, and slope distribution.
-   **Semantic Inference**: Automatically detects environment types (High Mountain 🏔️, Forest 🌲, Coastal 🌊) and technicity levels.
-   **Effort Calculation**: Estimates effort points (ITRA-like) and biological cost.

### 🧠 AI-Powered Insights (Gemini Integration)
-   **Smart Descriptions**: Generates rich, human-readable descriptions of tracks based on raw GPX data.
-   **Gear Recommendations**: Suggests equipment (e.g., "Poles recommended", "Headlamp required") based on terrain and estimated duration.
-   **Contextual Tags**: Automatically tags tracks with relevant keywords (e.g., "Skyrunning", "Technical Descent").

### 🗺️ Community & Discovery
-   **Global Heatmap**: Visualize community activity worldwide.
-   **Smart Filters**: Search by "Sensation" (e.g., "Rolling hills" vs "Vertical kilometer") rather than just stats.
-   **Race Management**: Manage official race routes, editions, and compare user tracks against official paths.

---

## 🛠️ Technology Stack

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python) - Async, high-performance API.
-   **Database**: SQLAlchemy with SQLite (Dev) / PostgreSQL (Prod ready).
-   **Frontend**: Jinja2 Templates + [TailwindCSS](https://tailwindcss.com/) + Vanilla JS.
-   **Mapping**: [Leaflet.js](https://leafletjs.com/) with OpenStreetMap & CartoDB tiles.
-   **AI Engine**: Google Gemini API for semantic enrichment.
-   **Containerization**: Docker & Docker Compose.

---

## 🚀 Getting Started

### Prerequisites
-   **Docker** & **Docker Compose** (Recommended)
-   *Or* Python 3.9+ for local development.

### 🐳 Run with Docker

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd KairnGpx
    ```

2.  **Start the application**
    ```bash
    docker-compose up -d --build
    ```

3.  **Access the app**
    Open your browser at `http://localhost:8090` (Note: internal port 8000 is mapped to 8090).

### 🔧 Local Development (No Docker)

1.  **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Windows: venv\Scripts\activate
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment**
    Create a `.env` file (optional for local dev, defaults are provided in `main.py`):
    ```ini
    # Example .env
    GEMINI_API_KEY=your_api_key_here
    SECRET_KEY=dev_secret_key
    ```

4.  **Run the Server**
    ```bash
    uvicorn app.main:app --reload --port 8000
    ```

---

## 📂 Project Structure

```bash
Kairn/
├── app/
│   ├── main.py            # Application Entry Point & Routes
│   ├── models.py          # Database Schema (SQLAlchemy)
│   ├── services/          # Business Logic
│   │   ├── analytics.py   # GPX Parsing & Math
│   │   ├── ai_analyzer.py # Gemini AI Integration
│   │   └── prediction.py  # Race Time Estimation
│   ├── templates/         # HTML (Jinja2)
│   ├── static/            # CSS, JS, Images
│   └── uploads/           # GPX File Storage
├── docs/                  # Documentation & Screenshots
├── docker-compose.yml     # Container Orchestration
├── Dockerfile             # Image Definition
└── deploy.sh              # Production Deployment Script
```

---

## 🔮 Roadmap

We are actively working on the "Premium Experience" for trail runners (see `docs/product_proposal.md`):

-   [ ] **3D Flyover**: Immersive 3D preview of tracks.
-   [ ] **Pacing Calculator**: Estimate finish time based on runner profile (ITRA index).
-   [ ] **Live Weather**: Weather forecasts for specific checkpoints (Start vs Summit).
-   [ ] **Virtual Cairns**: Community-placed markers for water sources, dangers, or viewpoints.
-   [ ] **Garmin/Suunto Sync**: Direct export to watch.

---

## 🤝 Contributing

Contributions are welcome!

1.  **Fork the Project**
2.  **Create your Feature Branch** (`git checkout -b feature/AmazingFeature`)
3.  **Commit your Changes** (`git commit -m 'Add some AmazingFeature'`)
4.  **Push to the Branch** (`git push origin feature/AmazingFeature`)
5.  **Open a Pull Request**

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ for the trail community.*
