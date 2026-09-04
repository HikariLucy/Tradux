"""Domain models representing structured documents independent of any PDF engine."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BoundingBox(BaseModel):
    """Bounding box geometry in PDF points using (x0, y0, x1, y1) convention.

    Coordinates follow standard PDF page coordinate space:
    - x0, y0: top-left corner
    - x1, y1: bottom-right corner
    Validation ensures x1 >= x0 and y1 >= y0.
    """

    model_config = ConfigDict(frozen=True)

    x0: float = Field(..., description="Left coordinate in PDF points")
    y0: float = Field(..., description="Top coordinate in PDF points")
    x1: float = Field(..., description="Right coordinate in PDF points")
    y1: float = Field(..., description="Bottom coordinate in PDF points")

    @model_validator(mode="after")
    def validate_coordinates(self) -> "BoundingBox":
        """Verify that bottom-right is not less than top-left."""
        if self.x1 < self.x0:
            raise ValueError(f"Invalid bounding box: x1 ({self.x1}) < x0 ({self.x0})")
        if self.y1 < self.y0:
            raise ValueError(f"Invalid bounding box: y1 ({self.y1}) < y0 ({self.y0})")
        return self

    @property
    def width(self) -> float:
        """Return width in PDF points."""
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        """Return height in PDF points."""
        return self.y1 - self.y0

    def as_tuple(self) -> tuple[float, float, float, float]:
        """Return coordinates as (x0, y0, x1, y1) tuple."""
        return (self.x0, self.y0, self.x1, self.y1)


class TextSpan(BaseModel):
    """Smallest unit of continuous text sharing identical typographic styling."""

    text: str = Field(..., description="Verbatim text content of the span")
    bbox: BoundingBox = Field(..., description="Bounding box of the span")
    font_name: str = Field(..., description="Name of the font")
    font_size: float = Field(..., description="Font size in points")
    color: str = Field(
        ...,
        description="Normalized color in canonical uppercase hex format (#RRGGBB)",
    )
    flags: int = Field(
        default=0,
        description="Typographic flags from PDF engine (bold, italic, etc.) as integer",
    )
    origin: tuple[float, float] | None = Field(
        default=None,
        description="Typographic origin (baseline start x, y) if available",
    )


class TextLine(BaseModel):
    """A horizontal or directional line of text containing one or more spans."""

    text: str = Field(..., description="Reconstructed verbatim text of the line")
    bbox: BoundingBox = Field(..., description="Bounding box enclosing all spans")
    spans: list[TextSpan] = Field(
        default_factory=list,
        description="Ordered list of text spans in this line",
    )


class TextBlock(BaseModel):
    """A structural block of text composed of multiple lines."""

    text: str = Field(..., description="Reconstructed verbatim text of the block")
    bbox: BoundingBox = Field(..., description="Bounding box enclosing all lines")
    lines: list[TextLine] = Field(
        default_factory=list,
        description="Ordered list of lines in this block",
    )
    reading_order: int = Field(
        ...,
        description="0-indexed sequential reading order within the page",
    )
    block_type: str = Field(
        default="text",
        description="Block classification (e.g. text)",
    )


class ImageElement(BaseModel):
    """Reference to an image placed on a document page.

    Images are tracked per occurrence; repeated occurrences of the same image
    xref on a page or across pages are represented as distinct instances with
    unique deterministic image_ids and their respective bounding boxes.
    """

    image_id: str = Field(
        ...,
        description=(
            "Deterministic occurrence ID, formatted as p{page:03d}-img{index:03d}"
        ),
    )
    bbox: BoundingBox | None = Field(
        default=None,
        description="Placement bounding box on the page in PDF points",
    )
    width: int | None = Field(
        default=None,
        description="Native pixel width of the image if known",
    )
    height: int | None = Field(
        default=None,
        description="Native pixel height of the image if known",
    )
    xref: int | None = Field(
        default=None,
        description="PDF internal cross-reference number if available",
    )
    format: str | None = Field(
        default=None,
        description="Image format/extension (e.g. 'png', 'jpeg') if known",
    )


class Page(BaseModel):
    """A single page of a document."""

    page_number: int = Field(
        ...,
        ge=1,
        description="1-indexed page number according to human/domain convention",
    )
    width: float = Field(
        ...,
        description="Unrotated page width in PDF points (matches bbox space)",
    )
    height: float = Field(
        ...,
        description="Unrotated page height in PDF points (matches bbox space)",
    )
    rotation: int = Field(
        default=0,
        description="Page rotation angle in degrees (0, 90, 180, 270)",
    )
    blocks: list[TextBlock] = Field(
        default_factory=list,
        description="Ordered list of text blocks extracted from this page",
    )
    images: list[ImageElement] = Field(
        default_factory=list,
        description="List of image occurrences placed on this page",
    )


class Document(BaseModel):
    """Domain model representing a complete parsed document."""

    filename: str | None = Field(
        default=None,
        description="Original or logical filename of the document",
    )
    page_count: int = Field(
        default=0,
        ge=0,
        description="Total number of pages; automatically synced with len(pages)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="PDF document metadata dictionary (title, author, etc.)",
    )
    pages: list[Page] = Field(
        default_factory=list,
        description="Ordered list of pages in the document",
    )

    @model_validator(mode="after")
    def sync_page_count(self) -> "Document":
        """Ensure page_count and len(pages) are strictly consistent."""
        actual_pages = len(self.pages)
        if self.page_count == 0 and actual_pages > 0:
            object.__setattr__(self, "page_count", actual_pages)
        elif self.page_count != actual_pages:
            raise ValueError(
                f"page_count ({self.page_count}) does not match "
                f"actual pages ({actual_pages})"
            )
        return self

    def to_json(self, indent: int | None = None) -> str:
        """Serialize document to JSON string using Pydantic canonical serializer."""
        return self.model_dump_json(indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "Document":
        """Deserialize document using Pydantic canonical deserializer."""
        return cls.model_validate_json(json_str)
