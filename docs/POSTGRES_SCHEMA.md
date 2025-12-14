# Schéma Base de Données PostgreSQL

Ce document décrit le schéma idéal pour une migration de Kairn vers PostgreSQL.

## Extensions PostgreSQL requises

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis"; -- Pour la gestion spatiale avancée (optionnel mais recommandé)
```

## Types Énumérés (Enums)

PostgreSQL gère nativement les ENUMs, ce qui est plus performant que les chaînes de caractères.

```sql
CREATE TYPE activity_type AS ENUM (
    'TRAIL_RUNNING', 'RUNNING', 'HIKING', 'MTB_CROSS_COUNTRY',
    'MTB_ENDURO', 'GRAVEL', 'ROAD_CYCLING', 'ALPINISM', 'SKI_TOURING', 'OTHER'
);

CREATE TYPE status_enum AS ENUM ('TRAINING', 'RACE');
CREATE TYPE source_type AS ENUM ('UPLOAD', 'STRAVA_IMPORT', 'GARMIN_IMPORT', 'MANUAL_DRAW');
CREATE TYPE visibility_type AS ENUM ('PUBLIC', 'PRIVATE', 'UNLISTED');
CREATE TYPE verification_status AS ENUM ('PENDING', 'VERIFIED_ALGO', 'VERIFIED_HUMAN', 'REJECTED');
CREATE TYPE route_type AS ENUM ('LOOP', 'OUT_AND_BACK', 'POINT_TO_POINT');
CREATE TYPE race_status AS ENUM ('UPCOMING', 'COMPLETED', 'CANCELLED');
CREATE TYPE user_role AS ENUM ('user', 'moderator', 'admin', 'super_admin');
```

## Tables

### 1. Users

Utilisation de UUID pour les IDs pour une meilleure sécurité et scalabilité.

```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,

    role user_role DEFAULT 'user',
    is_premium BOOLEAN DEFAULT FALSE,

    -- Profil
    full_name VARCHAR(100),
    bio TEXT,
    location VARCHAR(100),
    website VARCHAR(255),
    strava_url VARCHAR(255),
    social_links JSONB DEFAULT '{}', -- Utilisation de JSONB pour les recherches performantes
    profile_picture_url VARCHAR(255),

    -- Physio (Séparable dans une table 'athlete_profiles' si ça grossit)
    age INTEGER,
    height INTEGER,
    weight DECIMAL(5,2),
    gender VARCHAR(20),
    max_heart_rate INTEGER,
    resting_heart_rate INTEGER,
    vo2_max DECIMAL(5,2),

    -- Community
    club_affiliation VARCHAR(100),
    is_certified_guide BOOLEAN DEFAULT FALSE,

    -- Performance
    itra_score INTEGER,
    utmb_index INTEGER,
    betrail_score DECIMAL(10,2),
    favorite_activity activity_type,
    achievements JSONB DEFAULT '[]',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);
```

### 2. Tracks

La table principale. Si PostGIS est utilisé, les colonnes `start_lat/lon` peuvent être remplacées par une colonne `geometry(Point, 4326)`.

```sql
CREATE TABLE tracks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    slug VARCHAR(255) UNIQUE NOT NULL,

    -- Relations
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    uploader_name VARCHAR(100) DEFAULT 'anonymous',

    -- Meta
    title VARCHAR(255) NOT NULL,
    description TEXT,
    source_type source_type DEFAULT 'UPLOAD',
    file_path VARCHAR(500) NOT NULL,
    file_hash VARCHAR(64) UNIQUE NOT NULL, -- SHA256

    visibility visibility_type DEFAULT 'PUBLIC',
    verification_status verification_status DEFAULT 'PENDING',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

    -- Activity
    activity_type activity_type DEFAULT 'TRAIL_RUNNING',
    technical_rating_context JSONB,

    -- Metrics
    distance_km DECIMAL(10, 3),
    elevation_gain INTEGER,
    elevation_loss INTEGER,
    max_altitude INTEGER,
    min_altitude INTEGER,
    avg_altitude INTEGER,
    max_slope DECIMAL(5,2),
    avg_slope_uphill DECIMAL(5,2),
    longest_climb INTEGER,

    -- Effort
    itra_points_estim INTEGER,
    km_effort DECIMAL(10, 2),
    ibp_index INTEGER,

    -- Terrain (JSONB allows indexing specific keys if needed)
    surface_composition JSONB, -- { "asphalt": 10, "trail": 90 }
    path_type JSONB,
    environment JSONB, -- ["high_mountain", "forest"]

    -- Logistics
    route_type route_type DEFAULT 'LOOP',

    -- Geo (Optimisation PostGIS possible ici)
    start_lat DECIMAL(9,6),
    start_lon DECIMAL(9,6),
    end_lat DECIMAL(9,6),
    end_lon DECIMAL(9,6),

    location_city VARCHAR(100),
    location_region VARCHAR(100),
    location_country VARCHAR(100),
    cities_crossed JSONB,

    -- Ratings
    technicity_score DECIMAL(5,2),
    water_points_count INTEGER DEFAULT 0,
    estimated_times JSONB,
    gear_requirements JSONB,
    accessibility JSONB,
    restrictions JSONB,

    -- Aesthetics
    best_season JSONB,
    scenery_rating INTEGER,
    mud_index VARCHAR(50),
    exposure VARCHAR(50),
    tags JSONB,

    -- Race Link
    is_official_route BOOLEAN DEFAULT FALSE
);

CREATE INDEX idx_tracks_location ON tracks(location_city, location_region);
CREATE INDEX idx_tracks_geo ON tracks(start_lat, start_lon); -- Ou index spatial GIST si PostGIS
CREATE INDEX idx_tracks_metrics ON tracks(distance_km, elevation_gain);
CREATE INDEX idx_tracks_user ON tracks(user_id);
```

### 3. Race Events (Hiérarchie des Courses)

```sql
CREATE TABLE race_events (
    id SERIAL PRIMARY KEY, -- Integer is fine for events unless massive scale
    slug VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255) NOT NULL,
    website VARCHAR(255),
    description TEXT,
    region VARCHAR(100),
    circuit VARCHAR(100), -- "UTMB World Series"
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

### 4. Race Editions

```sql
CREATE TABLE race_editions (
    id SERIAL PRIMARY KEY,
    event_id INTEGER REFERENCES race_events(id) ON DELETE CASCADE,
    year INTEGER NOT NULL,
    start_date DATE,
    end_date DATE,
    status race_status DEFAULT 'UPCOMING',

    UNIQUE(event_id, year)
);
```

### 5. Race Routes

Lien entre une édition et une trace GPX officielle.

```sql
CREATE TABLE race_routes (
    id SERIAL PRIMARY KEY,
    edition_id INTEGER REFERENCES race_editions(id) ON DELETE CASCADE,

    name VARCHAR(255) NOT NULL, -- "OCC", "CCC"
    distance_category VARCHAR(50), -- "50K", "100M"

    official_track_id UUID REFERENCES tracks(id) ON DELETE SET NULL,

    -- Redondance pour affichage rapide sans jointure complexe ou si trace manquante
    distance_km DECIMAL(10,3),
    elevation_gain INTEGER,

    results_url VARCHAR(255)
);
```

### 6. Event Requests

```sql
CREATE TABLE event_requests (
    id SERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    event_name VARCHAR(255) NOT NULL,
    year INTEGER,
    website VARCHAR(255),
    comment TEXT,
    status VARCHAR(50) DEFAULT 'PENDING', -- PENDING, APPROVED, REJECTED
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
```

## Recommandations de Migration (SQLAlchemy)

1.  **Changer le driver** : Utiliser `asyncpg` ou `psycopg2` au lieu de `sqlite`.
2.  **Types de colonnes** :
    *   Remplacer `Column(JSON)` par `Column(JSONB)`.
    *   Remplacer `Column(String)` pour les dates par `Column(DateTime(timezone=True))`.
    *   Utiliser `server_default=func.now()` pour les timestamps.
3.  **Indexation** : Ajouter des index GIN sur les colonnes JSONB souvent requêtées (comme `tags` ou `environment`).

---
*Schéma conçu pour assurer l'intégrité des données, la performance des recherches géographiques et textuelles, et l'évolutivité.*
