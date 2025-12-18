-- Create Track Reviews Table
CREATE TABLE IF NOT EXISTS track_reviews (
    id SERIAL PRIMARY KEY,
    track_id INTEGER REFERENCES tracks(id),
    user_id INTEGER REFERENCES users(id),
    rating INTEGER NOT NULL,
    comment TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc')
);

-- Create Track Executions Table
CREATE TABLE IF NOT EXISTS track_executions (
    id SERIAL PRIMARY KEY,
    track_id INTEGER REFERENCES tracks(id),
    user_id INTEGER REFERENCES users(id),
    duration_seconds INTEGER NOT NULL,
    execution_date TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc'),
    comment TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT (now() AT TIME ZONE 'utc')
);
