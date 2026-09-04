"""Domain models representing layout calculation results without PDF engine deps."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import BoundingBox


class LayoutStatus(StrEnum):
    """Status of text layout adjustment for a block."""

    FIT = "fit"
    SHRUNK = "shrunk"
    EXPANDED = "expanded"
    REVIEW_REQUIRED = "review_required"
    SKIPPED = "skipped"


class BlockLayout(BaseModel):
    """Detailed layout calculation and typographic plan for a single text block."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(..., description="1-indexed page number of the block")
    reading_order: int = Field(
        ...,
        description="0-indexed reading order within the page",
    )
    bbox: BoundingBox = Field(
        ...,
        description="Original bounding box in unrotated canonical space",
    )
    render_bbox: BoundingBox = Field(
        ...,
        description="Final bounding box where translated text will be rendered",
    )
    text: str = Field(
        ...,
        description="Text content planned for rendering (e.g. translated text)",
    )
    original_font_name: str = Field(
        ...,
        description="Dominant original font name extracted from source block",
    )
    resolved_font_name: str = Field(
        ...,
        description="Standard or available font name chosen for rendering",
    )
    original_font_size: float = Field(
        ...,
        description="Representative font size in points from source block",
    )
    final_font_size: float = Field(
        ...,
        description="Final font size in points after layout adjustment",
    )
    color: str = Field(
        ...,
        description="Text color in canonical uppercase hex format (#RRGGBB)",
    )
    line_height: float = Field(
        ...,
        description="Line height / leading factor applied during rendering",
    )
    status: LayoutStatus = Field(
        ...,
        description="Outcome of layout adjustment (fit, shrunk, expanded, etc.)",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Structured warnings recorded during layout calculation",
    )
    is_font_substituted: bool = Field(
        default=False,
        description="Whether a fallback font had to be substituted for the original",
    )
    lines_count: int | None = Field(
        default=None,
        description="Approximate or calculated line count after wrapping if available",
    )


class PageLayout(BaseModel):
    """Layout calculations for all blocks on a single page."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(..., description="1-indexed page number")
    blocks: list[BlockLayout] = Field(
        default_factory=list,
        description="Ordered list of block layouts on this page",
    )


class LayoutStats(BaseModel):
    """Aggregate statistics summarizing layout outcomes across a document."""

    model_config = ConfigDict(frozen=True)

    total_blocks: int = Field(default=0, description="Total text blocks evaluated")
    fit_count: int = Field(
        default=0,
        description="Blocks fitting with original font size",
    )
    shrunk_count: int = Field(
        default=0,
        description="Blocks fitting after controlled font reduction",
    )
    expanded_count: int = Field(
        default=0,
        description="Blocks fitting after safe vertical bbox expansion",
    )
    review_required_count: int = Field(
        default=0,
        description="Blocks that could not fit legibly within limits",
    )
    skipped_count: int = Field(
        default=0,
        description="Blocks without translation or skipped",
    )
    font_substitutions: int = Field(
        default=0,
        description="Count of blocks where font substitution was applied",
    )


class DocumentLayout(BaseModel):
    """Complete document layout plan ready for rendering."""

    model_config = ConfigDict(frozen=True)

    pages: list[PageLayout] = Field(
        default_factory=list,
        description="List of page layouts in sequential order",
    )
    stats: LayoutStats = Field(
        default_factory=LayoutStats,
        description="Aggregate layout statistics",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional execution metadata (timing, config summary, etc.)",
    )

    def to_json(self, **kwargs: Any) -> str:
        """Serialize DocumentLayout to a JSON string."""
        return self.model_dump_json(**kwargs)

    @classmethod
    def from_json(cls, json_str: str) -> "DocumentLayout":
        """Deserialize DocumentLayout from a JSON string."""
        return cls.model_validate_json(json_str)
