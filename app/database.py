import os
import sys
import time
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get DATABASE_URL from environment (will be used by settings)
# This is a fallback if settings are not available during early initialization
DATABASE_URL = os.getenv("DATABASE_URL")

# Use SQLite memory database for testing if no URL is provided
if not DATABASE_URL:
    DATABASE_URL = "sqlite:///:memory:"
    print("No DATABASE_URL provided, using in-memory SQLite for testing")

# Ensure the URL uses the correct psycopg3 driver
if DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://")

# Debug print to diagnose connection issues
print(f"Connecting to database with URL: {DATABASE_URL}")

# Determine if we're in a testing environment
is_testing = "pytest" in sys.modules or "import_test.py" in sys.argv[0]

# Create engine with retry logic for connection issues


def create_engine_with_retry(url, max_retries=10, retry_delay=3):
    """Create SQLAlchemy engine with retry logic for connection issues"""
    logger = logging.getLogger("streamvault")

    for attempt in range(max_retries):
        try:
            if url.startswith("sqlite"):
                engine = create_engine(url, future=True, connect_args={"check_same_thread": False})
            else:
                engine = create_engine(
                    url,
                    future=True,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_recycle=1800,  # Recycle connections after 30 minutes (was 1 hour)
                    pool_size=20,  # Reduce pool size for better resource management
                    max_overflow=50,  # Reduce overflow but still handle spikes
                    pool_timeout=15,  # Reduce timeout to fail faster and free resources
                    connect_args={"connect_timeout": 5, "application_name": "StreamVault"},  # Reduce connect timeout
                )

            # Test the connection
            with engine.connect() as conn:
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


def get_database_url():
    """
    Retrieve the validated database URL for connections.

    This function provides a centralized way to access the database URL with proper
    validation and environment-specific handling. It ensures the URL is properly
    configured and handles testing scenarios appropriately.

    Returns:
        str: The validated database URL.

    Raises:
        ValueError: If DATABASE_URL is not configured properly.
    """
    logger = logging.getLogger("streamvault")

    # Try to get from settings first, fallback to environment variable
    try:
        from app.config.settings import settings

        url = settings.DATABASE_URL
        if not url:
            url = DATABASE_URL  # Fallback to module-level variable
    except ImportError:
        # During early initialization, settings might not be available
        url = DATABASE_URL

    # Validate the DATABASE_URL
    if not url:
        logger.error("DATABASE_URL is not set. Ensure the environment variable is configured.")
        raise ValueError("DATABASE_URL is not set.")

    # Environment-specific overrides
    if is_testing:
        logger.info("Using in-memory SQLite database for testing.")
        return "sqlite:///:memory:"

    # Ensure the URL uses the correct psycopg3 driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://")

    # Log the final URL for debugging (mask sensitive information)
    masked_url = url
    if "@" in url:
        # Mask password in URL for security
        parts = url.split("@")
        if len(parts) > 1:
            auth_part = parts[0]
            if ":" in auth_part:
                protocol_user = auth_part.rsplit(":", 1)[0]
                masked_url = f"{protocol_user}:***@{parts[1]}"

    logger.debug(f"Using database URL: {masked_url}")
    return url


def get_db():
    """Enhanced database session with better error handling and resource cleanup"""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger = logging.getLogger("streamvault")
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        try:
            db.close()
        except Exception as e:
            logger = logging.getLogger("streamvault")
            logger.warning(f"Error closing database session: {e}")
