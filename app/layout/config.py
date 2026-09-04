"""Configuration parameters for the LayoutEngine text reflow and fitting."""

from pydantic import BaseModel, ConfigDict, Field


class LayoutConfig(BaseModel):
    """Configurable thresholds and options for layout fitting and reflow."""

    model_config = ConfigDict(frozen=True)

    min_font_size: float = Field(
        default=7.0,
        gt=0.0,
        description="Absolute minimum font size in points allowed during shrink",
    )
    min_font_scale: float = Field(
        default=0.75,
        gt=0.0,
        le=1.0,
        description="Minimum scale relative to original font size (0.75 = 75%)",
    )
    font_size_step: float = Field(
        default=0.5,
        gt=0.0,
        description="Step decrement in points when iteratively shrinking font size",
    )
    default_line_height: float = Field(
        default=1.15,
        gt=0.0,
        description="Default line height / leading factor for multiline text wrapping",
    )
    min_line_height: float = Field(
        default=0.95,
        gt=0.0,
        description="Minimum line height factor allowed when tightening lines",
    )
    line_height_step: float = Field(
        default=0.05,
        gt=0.0,
        description="Step decrement when iteratively adjusting line height",
    )
    allow_safe_vertical_expansion: bool = Field(
        default=True,
        description="Whether to attempt safe box expansion when shrink is insufficient",
    )
    max_vertical_expansion_ratio: float = Field(
        default=0.50,
        ge=0.0,
        description="Maximum vertical expansion as a fraction of height (0.50 = 50%)",
    )
    max_vertical_expansion_pt: float = Field(
        default=30.0,
        ge=0.0,
        description="Absolute cap on vertical expansion in PDF points",
    )
    page_margin_pt: float = Field(
        default=10.0,
        ge=0.0,
        description="Minimum clearance in points from page boundaries during expansion",
    )
    geometric_tolerance_pt: float = Field(
        default=0.5,
        ge=0.0,
        description="Geometric tolerance in points for boundary and collision checks",
    )
