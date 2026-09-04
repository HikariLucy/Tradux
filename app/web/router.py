"""Web router serving the Tradux Web Workbench."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

router = APIRouter(include_in_schema=False)


@router.get("/", response_class=HTMLResponse)
async def get_workbench(request: Request) -> HTMLResponse:
    """Render the Tradux Web Workbench desktop interface."""
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="workbench.html",
        context={
            "app_name": settings.app_name,
            "app_version": settings.app_version,
        },
    )
