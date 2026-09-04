"""Deterministic representative style selection for heterogeneous text blocks."""

from collections import defaultdict

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import TextBlock


class RepresentativeStyle(BaseModel):
    """Dominant typographic style selected for a TextBlock."""

    model_config = ConfigDict(frozen=True)

    font_name: str = Field(..., description="Dominant font name")
    font_size: float = Field(..., description="Representative font size in points")
    color: str = Field(..., description="Dominant color in #RRGGBB format")
    is_bold: bool = Field(default=False, description="Whether dominant style is bold")
    is_italic: bool = Field(
        default=False, description="Whether dominant style is italic"
    )


def select_representative_style(block: TextBlock) -> RepresentativeStyle:
    """Select the representative typographic style for a TextBlock deterministically.

    Inspects all spans within the block's lines. Spans with non-empty content
    are weighted by character count. The style tuple with the greatest character
    count is selected. In case of ties, the style appearing earlier in reading
    order is chosen.

    Args:
        block: TextBlock from DocumentModel.

    Returns:
        RepresentativeStyle with dominant font, size, color, bold, and italic flags.
    """
    # Fallback defaults if block contains no spans
    default_font = "Helvetica"
    default_size = 11.0
    default_color = "#000000"

    spans_with_text: list[tuple[str, float, str, int, int]] = []
    for line in block.lines:
        for span in line.spans:
            text = span.text.strip()
            if text:
                spans_with_text.append(
                    (
                        span.font_name,
                        span.font_size,
                        span.color,
                        span.flags,
                        len(span.text),
                    )
                )

    if not spans_with_text:
        # If all spans are empty whitespace, check if any span exists at all
        for line in block.lines:
            if line.spans:
                s = line.spans[0]
                is_b = bool(s.flags & 16)
                is_i = bool(s.flags & 2)
                return RepresentativeStyle(
                    font_name=s.font_name or default_font,
                    font_size=s.font_size or default_size,
                    color=s.color or default_color,
                    is_bold=is_b,
                    is_italic=is_i,
                )
        return RepresentativeStyle(
            font_name=default_font,
            font_size=default_size,
            color=default_color,
            is_bold=False,
            is_italic=False,
        )

    # Accumulate character weight per distinct style tuple
    # Key: (font_name, round(font_size, 1), color, is_bold, is_italic)
    weights: dict[tuple[str, float, str, bool, bool], int] = defaultdict(int)
    first_seen: dict[tuple[str, float, str, bool, bool], int] = {}

    for idx, (f_name, f_size, color, flags, char_count) in enumerate(spans_with_text):
        is_bold = bool(flags & 16)
        is_italic = bool(flags & 2)
        # Rounded size to avoid micro float discrepancies
        style_key = (f_name, round(f_size, 2), color.upper(), is_bold, is_italic)
        weights[style_key] += char_count
        if style_key not in first_seen:
            first_seen[style_key] = idx

    # Deterministic sort: greatest character weight, then smallest first_seen index
    sorted_styles = sorted(
        weights.keys(),
        key=lambda k: (-weights[k], first_seen[k]),
    )

    dominant_key = sorted_styles[0]
    return RepresentativeStyle(
        font_name=dominant_key[0],
        font_size=dominant_key[1],
        color=dominant_key[2],
        is_bold=dominant_key[3],
        is_italic=dominant_key[4],
    )
