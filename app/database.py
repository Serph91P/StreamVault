import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

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

# Create engine with connect_args for SQLite to avoid locking issues in tests
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(DATABASE_URL, future=True, connect_args={'check_same_thread': False})
else:
    engine = create_engine(DATABASE_URL, future=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()