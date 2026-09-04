"""Aggregated API routers."""

from fastapi import APIRouter

from app.api.v1.capabilities import router as capabilities_router
from app.api.v1.documents import router as documents_router
from app.api.v1.health import router as health_router
from app.api.v1.jobs import router as jobs_router
from app.api.v1.workbench import router as workbench_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(capabilities_router)
api_router.include_router(documents_router)
api_router.include_router(jobs_router)
api_router.include_router(workbench_router)
