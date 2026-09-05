"""Domain models and schemas for translation jobs."""

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class JobStatus(StrEnum):
    """Execution status of a translation job."""

    CREATED = "created"
    ANALYZING = "analyzing"
    TRANSLATING = "translating"
    LAYOUT = "layout"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Check if job has reached a terminal state."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED)


class JobMode(StrEnum):
    """Operating mode of a translation job."""

    DEMO = "demo"
    CONFIGURED = "configured"


SUPPORTED_LANGUAGES: frozenset[str] = frozenset(
    {"nl", "en", "de", "fr", "es", "pt", "it"}
)


class JobLayoutStats(BaseModel):
    """Layout engine metrics for the job result."""

    model_config = ConfigDict(frozen=True)

    fit_count: int = Field(
        default=0,
        description="Blocks fitted at original or slightly reduced line height",
    )
    shrunk_count: int = Field(
        default=0,
        description="Blocks fitted after font shrinking",
    )
    expanded_count: int = Field(
        default=0,
        description="Blocks fitted after safe vertical expansion",
    )
    review_required_count: int = Field(
        default=0,
        description="Blocks that could not fit without overflow",
    )


class Job(BaseModel):
    """Internal domain model representing a translation job in memory."""

    model_config = ConfigDict(validate_assignment=True)

    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.CREATED
    stage: str = "created"
    stage_message: str = "Trabajo recibido"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    filename: str
    source_language: str | None = None
    detected_source_language: str | None = None
    target_language: str
    mode: JobMode
    provider: str
    protected_terms: list[str] = Field(default_factory=list)
    page_count: int | None = None
    total_blocks: int | None = None
    translated_blocks: int | None = None
    layout_stats: JobLayoutStats | None = None
    result_available: bool = False
    error_code: str | None = None
    error_message: str | None = None


class JobResponse(BaseModel):
    """Safe public API representation of a translation job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: str
    status: JobStatus
    stage: str
    stage_message: str
    created_at: datetime
    updated_at: datetime
    filename: str
    source_language: str | None = None
    detected_source_language: str | None = None
    target_language: str
    mode: JobMode
    provider: str
    page_count: int | None = None
    total_blocks: int | None = None
    translated_blocks: int | None = None
    layout_stats: JobLayoutStats | None = None
    result_available: bool = False
    error_code: str | None = None
    error_message: str | None = None


class JobCreateResponse(BaseModel):
    """Response returned upon successfully accepting a job creation request."""

    job_id: str
    status: JobStatus
    stage: str
    stage_message: str
    status_url: str
    result_url: str
