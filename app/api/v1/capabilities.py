"""API endpoints for exposing safe server capabilities without revealing secrets."""

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.jobs.service import check_configured_provider_available

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


class ServerCapabilitiesResponse(BaseModel):
    """Safe server capabilities information for the frontend client."""

    model_config = ConfigDict(frozen=True)

    demo_translation: bool = Field(
        default=True,
        description="Demo translation with MockTranslator is always available",
    )
    configured_translation_available: bool = Field(
        ...,
        description="True if an external provider is configured with credentials",
    )
    configured_provider: str = Field(
        ...,
        description="Logical name of the configured translation provider",
    )
    max_upload_size_mb: int = Field(
        ...,
        description="Maximum upload file size limit in megabytes",
    )


@router.get(
    "",
    response_model=ServerCapabilitiesResponse,
    summary="Get server capabilities",
    description=(
        "Returns public safe capabilities and limits of the server. "
        "Never exposes API keys, endpoints, or confidential configuration."
    ),
)
async def get_capabilities() -> ServerCapabilitiesResponse:
    """Return safe capabilities metadata."""
    settings = get_settings()
    available, provider_name = check_configured_provider_available(settings)
    return ServerCapabilitiesResponse(
        demo_translation=True,
        configured_translation_available=available,
        configured_provider=provider_name,
        max_upload_size_mb=settings.max_upload_size_mb,
    )
