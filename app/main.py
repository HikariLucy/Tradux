"""Main FastAPI application entrypoint for Tradux."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.web.router import STATIC_DIR
from app.web.router import router as web_router


def create_app() -> FastAPI:
    """Initialize and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Servicio de traducción de documentos preservando maquetación",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        debug=settings.debug,
    )

    # Mount /health directly at root as required
    application.include_router(health_router)

    # Mount versioned API routes under configured prefix
    application.include_router(api_router, prefix=settings.api_v1_prefix)

    # Mount static files for Web Workbench
    application.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    # Mount web workbench interface at root
    application.include_router(web_router)

    return application


app = create_app()
