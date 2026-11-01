"""Liveness and readiness endpoints for local development and orchestration."""

import logging

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import engine

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("/live", summary="Liveness check")
def liveness() -> dict[str, str]:
    """Report that the API process is running; this does not test dependencies."""
    return {"status": "alive", "service": "api", "version": settings.app_version}


@router.get("/ready", summary="Readiness check")
def readiness() -> dict[str, str]:
    """Report readiness only when PostgreSQL accepts a simple query."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("Readiness check failed: database is unavailable (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from None
    return {"status": "ready", "service": "api", "database": "reachable"}
