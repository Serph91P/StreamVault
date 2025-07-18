import os
import sys
import time
import logging
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

DATABASE_URL = os.getenv('DATABASE_URL')

# Use SQLite memory database for testing if no URL is provided
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///:memory:"
    print("No DATABASE_URL provided, using in-memory SQLite for testing")

# Ensure the URL uses the correct psycopg3 driver
if DATABASE_URL and DATABASE_URL.startswith('postgresql://'):
    DATABASE_URL = DATABASE_URL.replace('postgresql://', 'postgresql+psycopg://')

# Debug print to diagnose connection issues
print(f"Connecting to database with URL: {DATABASE_URL}")

# Determine if we're in a testing environment
is_testing = 'pytest' in sys.modules or 'import_test.py' in sys.argv[0]

# Create engine with retry logic for connection issues
def create_engine_with_retry(url, max_retries=10, retry_delay=3):
    """Create SQLAlchemy engine with retry logic for connection issues"""
    logger = logging.getLogger("streamvault")
    
    for attempt in range(max_retries):
        try:
            if url.startswith('sqlite'):
                engine = create_engine(url, future=True, connect_args={'check_same_thread': False})
            else:
                engine = create_engine(
                    url, 
                    future=True,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_recycle=3600,   # Recycle connections after 1 hour
                    pool_size=50,        # Increase pool size to handle more concurrent requests
                    max_overflow=100,    # Increase overflow to handle spikes
                    pool_timeout=30,     # Increase timeout to avoid premature failures
                    connect_args={
                        "connect_timeout": 10,
                        "application_name": "StreamVault"
                    }
                )
            
            # Test the connection
            with engine.connect() as conn:
                from sqlalchemy.sql import text
                conn.execute(text("SELECT 1"))
            
            logger.info(f"✅ Database connection established successfully on attempt {attempt + 1}")
            return engine
            
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"❌ Failed to connect to database after {max_retries} attempts: {e}")
                raise
            
            logger.warning(f"⚠️ Database connection attempt {attempt + 1} failed: {e}")
            logger.info(f"🔄 Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
    
    raise Exception("Could not establish database connection")

# Create engine with retry logic
engine = create_engine_with_retry(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
