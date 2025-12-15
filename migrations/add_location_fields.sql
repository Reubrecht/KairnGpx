-- Add missing columns to race_events table
ALTER TABLE race_events ADD COLUMN IF NOT EXISTS continent VARCHAR;
ALTER TABLE race_events ADD COLUMN IF NOT EXISTS country VARCHAR;
ALTER TABLE race_events ADD COLUMN IF NOT EXISTS department VARCHAR;
ALTER TABLE race_events ADD COLUMN IF NOT EXISTS massif VARCHAR;
ALTER TABLE race_events ADD COLUMN IF NOT EXISTS city VARCHAR;

-- Optional: Populate with default values or infer if possible (manual step usually)
-- UPDATE race_events SET country = 'France' WHERE country IS NULL; -- Example
