"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import logging
import re
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.auth import router as auth_router
from app.api.routes.archive import router as archive_router
from app.api.routes.reports import router as reports_router
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.documents import router as documents_router
from app.api.routes.shipments import router as shipments_router
from app.api.routes.health import router as health_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.imports import router as imports_router
from app.api.routes.exports import router as exports_router
from app.api.routes.finance import router as finance_router
from app.api.routes.master_data import router as master_data_router
from app.api.routes.organizations import router as organizations_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.request_context import request_id_context

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Application startup/shutdown hooks for centralized lifecycle management."""
    logger.info("Application startup: %s (%s)", settings.app_name, settings.app_env)
    yield
    logger.info("Application shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Versioned REST API foundation for international trade operations.",
    docs_url="/docs" if settings.app_env.lower() != "production" else None,
    redoc_url="/redoc" if settings.app_env.lower() != "production" else None,
    openapi_url="/openapi.json" if settings.app_env.lower() != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
)

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")


@app.middleware("http")
async def add_response_safety_headers(request: Request, call_next):
    """Attach safe defaults and a validated correlation ID to every API response."""
    supplied_request_id = request.headers.get("X-Request-ID", "")
    request_id = supplied_request_id if _REQUEST_ID_PATTERN.fullmatch(supplied_request_id) else str(uuid4())
    request.state.request_id = request_id
    context_token = request_id_context.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if request.url.path.startswith("/api/"):
            # Trade, financial, identity, and document responses are user- and tenant-specific.
            response.headers["Cache-Control"] = "no-store"
            response.headers["Pragma"] = "no-cache"
        return response
    finally:
        request_id_context.reset(context_token)

app.include_router(health_router, prefix="/api/v1")
app.include_router(reports_router, prefix="/api/v1")
app.include_router(archive_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(organizations_router, prefix="/api/v1")
app.include_router(master_data_router, prefix="/api/v1")
app.include_router(inventory_router, prefix="/api/v1")
app.include_router(imports_router, prefix="/api/v1")
app.include_router(exports_router, prefix="/api/v1")
app.include_router(finance_router, prefix="/api/v1")
app.include_router(shipments_router, prefix="/api/v1")
app.include_router(documents_router, prefix="/api/v1")
app.include_router(tasks_router, prefix="/api/v1")
app.include_router(approvals_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")


@app.get("/", tags=["system"], summary="API information")
def api_root() -> dict[str, str]:
    """Provide an API discovery response without exposing configuration secrets."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
        "docs": "/docs" if settings.app_env.lower() != "production" else "disabled",
        "health": "/api/v1/health/live",
    }
