# 🏔️ Kairn - Trail Running Community Platform

![License](https://img.shields.io/github/license/jreub/Kairn?style=for-the-badge&color=blue)
![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-07405E?style=for-the-badge&logo=sqlite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![TailwindCSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)
![Leaflet](https://img.shields.io/badge/Leaflet-199900?style=for-the-badge&logo=leaflet&logoColor=white)

**Kairn** is a modern web application designed for the trail running community to share, analyze, and discover GPX tracks. It goes beyond simple segments by offering semantic analysis of tracks (technicity, environment, terrain) and a community-driven catalog.

---

## 📸 Screenshots

### Dashboard & Activity Feed
![Dashboard](docs/screenshots/dashboard.webp)

### Explore & Discover Tracks
![Explore Page](docs/screenshots/explore.webp)

### Detailed Track Analysis
![Track Detail](docs/screenshots/track_detail.webp)

---

## ✨ Key Features

-   **🏃‍♂️ GPX Track Analysis**: Automatic calculation of distance, elevation gain, and detailed slope analysis.
-   **🧠 Semantic Attributes**: Automatic inference of track characteristics:
    -   **Environment**: High Mountain 🏔️, Forest 🌲, Coastal 🌊, etc.
    -   **Technicity**: Runnable vs Technical terrain based on slope and consistency.
-   **🔍 Advanced Exploration**:
    -   Filter by Technicity, Environment, Distance, Elevation.
    -   Interactive Global Heatmap 🗺️.
    -   Dual-slider filters for precise discovery.
-   **📱 Fully Responsive**: Optimized for Desktop and Mobile usage with a fluid UI.
-   **🔐 User System**: Secure account creation, login, and private/public track management.

## 🛠️ Technology Stack

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python) - High performance, easy to use.
-   **Database**: SQLAlchemy (SQLite for dev / PostgreSQL ready).
-   **Frontend**:
    -   **Templates**: Jinja2 (Server Side Rendering).
    -   **Styling**: [TailwindCSS](https://tailwindcss.com/).
    -   **Maps**: [Leaflet.js](https://leafletjs.com/) with OpenStreetMap & CartoDB tiles.
    -   **Interactivity**: Vanilla JS + [noUiSlider](https://refreshless.com/nouislider/).
-   **Deployment**: Docker & Docker Compose.

## 🚀 Getting Started

### Prerequisites

-   Docker & Docker Compose
-   *Or* Python 3.9+ for local dev.

### 🐳 Run with Docker (Recommended)

1.  **Clone the repository**
    ```bash
    git clone https://github.com/Reubrecht/KairnGpx.git
    cd Kairn
    ```

2.  **Start the container**
    ```bash
    docker-compose up -d --build
    ```

3.  **Access the app**
    Open your browser at `http://localhost:8000` (or your server IP).

### 🔧 Local Development

1.  **Create a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application**
    ```bash
    uvicorn app.main:app --reload
    ```

## 📂 Project Structure

```
Kairn/
├── app/
│   ├── main.py            # Application entry point & Routes
│   ├── models.py          # Database Models
│   ├── database.py        # DB Connection logic
│   ├── templates/         # HTML Jinja2 Templates
│   ├── static/            # CSS/JS assets
│   ├── services/
│   │   └── analytics.py   # GPX Analysis Logic
│   └── uploads/           # Storage for GPX files
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## 🤝 Contributing

Contributions are welcome!
1.  Fork the project.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes (`git commit -m 'Add some AmazingFeature'`).
4.  Push to the branch (`git push origin feature/AmazingFeature`).
5.  Open a Pull Request.

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
*Built with ❤️ for the trail community.*
