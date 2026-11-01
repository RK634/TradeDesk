"""SQLAlchemy engine and session factory."""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    # Keep database connections out of debug logs and avoid implicit autocommit.
    echo=False,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a session and always close it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
