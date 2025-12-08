# Kairn Trail Platform

Kairn is a web platform designed for trail runners to manage, analyze, and share their running tracks. It allows users to upload GPX files and automatically calculates key metrics such as distance, elevation, technicity, and effort.

## Features

- **User Management**: Secure registration and login system.
- **GPX Upload**: Upload GPX files to store your tracks.
- **Automatic Analysis**:
  - Distance, Elevation Gain/Loss.
  - Slope analysis (Max slope, Average uphill slope).
  - Effort calculation (Km Effort, ITRA points estimate).
  - Route type detection (Loop, Point-to-Point).
  - Estimated completion times for different runner levels (Hiker, Runner, Elite).
- **Geocoding**: Automatic detection of city and region from the track's starting point.
- **Track Organization**: Categorize tracks by technicity, terrain, and tags (High mountain, Coastal, etc.).
- **Search & Filtering**: Filter tracks by difficulty, city, or tags.

## Tech Stack

- **Backend**: Python 3, FastAPI
- **Database**: SQLite (Development), SQLAlchemy ORM
- **Templating**: Jinja2 (Server-side rendering)
- **Processing**: `gpxpy` for GPX parsing, `geopy` for geocoding
- **Containerization**: Docker, Docker Compose

## Getting Started

### Prerequisites

- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/) installed on your machine.

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd kairn-trail-platform
   ```

2. **Run the application:**
   You can use the provided deployment script or Docker Compose directly.

   Using the script:
   ```bash
   ./deploy.sh
   ```

   Or using Docker Compose:
   ```bash
   mkdir -p app/data app/uploads app/static
   docker-compose up -d --build
   ```

3. **Access the application:**
   Open your browser and navigate to:
   [http://localhost:8090](http://localhost:8090)

### Development

To run the application locally without Docker (requires Python 3.8+):

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the server:
   ```bash
   uvicorn app.main:app --reload --port 8090
   ```

## Project Structure

```
.
├── app/
│   ├── main.py             # Application entry point & routes
│   ├── models.py           # Database models
│   ├── database.py         # Database connection
│   ├── services/           # Business logic & services
│   │   └── analytics.py    # GPX analysis logic
│   ├── templates/          # HTML Templates
│   ├── static/             # Static files (CSS, JS, Images)
│   ├── uploads/            # Stored GPX files
│   └── data/               # SQLite database file
├── deploy.sh               # Deployment script
├── docker-compose.yml      # Docker configuration
└── requirements.txt        # Python dependencies
```

## License

[MIT](LICENSE)
