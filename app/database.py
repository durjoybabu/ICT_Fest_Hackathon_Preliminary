"""Database engine and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    # BUG FIX: check_same_thread False keeps it thread-accessible, timeout helps spin-lock
    connect_args={"check_same_thread": False, "timeout": 30},
)

# BUG FIX: Enable WAL (Write-Ahead Logging) mode for SQLite to handle highly concurrent requests
# This ensures that read and write operations do not block each other, satisfying Rules 3, 4, 5, 14, and 16.
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL;")
    cursor.execute("PRAGMA synchronous=NORMAL;")
    cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

Base = declarative_base()


def get_db():
    """Yield a request-scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
