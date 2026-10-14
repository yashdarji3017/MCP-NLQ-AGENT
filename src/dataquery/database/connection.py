"""Database connection manager with read-only session guarantees."""

import logging
from contextlib import contextmanager
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker
from dataquery.config import get_settings

logger = logging.getLogger(__name__)

_engine: Engine | None = None
_session_factory: sessionmaker | None = None


def get_engine() -> Engine:
    """Initialize or return cached SQLAlchemy engine configured for read-only safety."""
    global _engine
    if _engine is None:
        settings = get_settings()
        url = settings.DATABASE_URL
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)

        connect_args = {
            "connect_timeout": 5,
            "options": f"-c default_transaction_read_only=on -c statement_timeout={settings.QUERY_TIMEOUT_SECONDS * 1000}",
        }

        try:
            _engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
                pool_recycle=1800,
                connect_args=connect_args,
                execution_options={"isolation_level": "AUTOCOMMIT", "readonly": True},
            )
            logger.info("SQLAlchemy engine initialized with read-only transaction defaults.")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {type(e).__name__}")
            raise

    return _engine


@contextmanager
def get_db_connection() -> Generator:
    """Context manager providing a safe read-only database connection."""
    engine = get_engine()
    connection = engine.connect()
    try:
        connection.execute(text("SET TRANSACTION READ ONLY;"))
        yield connection
    finally:
        connection.close()


def test_db_connection() -> bool:
    """Test connectivity to the PostgreSQL database without throwing unhandled exceptions."""
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT 1;")).scalar()
            return result == 1
    except Exception as e:
        logger.warning(f"Database connectivity check failed (normal in offline/testing mode): {type(e).__name__}")
        return False
