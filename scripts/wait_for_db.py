import logging
import os
import sys
import time

import psycopg2

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("wait_for_db")

def wait_for_db():
    """Wait for postgres to become available"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("DATABASE_URL not set")
        sys.exit(1)

    # Simple parsing to extract connection params could be added here
    # But psycopg2.connect(dsn) handles the URL directly nicely.
    
    retries = 30
    while retries > 0:
        try:
            logger.info(f"Checking database connection... (Retries left: {retries})")
            conn = psycopg2.connect(db_url)
            conn.close()
            logger.info("Database is available!")
            return
        except psycopg2.OperationalError as e:
            logger.warning(f"Database unavailable: {e}")
            retries -= 1
            time.sleep(2)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            sys.exit(1)
            
    logger.error("Could not connect to database after many retries")
    sys.exit(1)

if __name__ == "__main__":
    wait_for_db()
