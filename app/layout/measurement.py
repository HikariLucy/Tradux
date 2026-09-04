"""Text measurement utilities using PyMuPDF Shape simulation."""

from typing import Any

import pymupdf


class TextMeasurer:
    """Measures whether text fits into a bounding box with specific typography.

    Operates in memory using uncommitted PyMuPDF Shape instances, ensuring
    exact font metrics and wrapping behavior without modifying any document.
    """

    def __init__(self) -> None:
        self._doc = pymupdf.open()
        self._page = self._doc.new_page(width=3000, height=3000)

    def measure(
        self,
        text: str,
        font_name: str,
        font_size: float,
        rect: tuple[float, float, float, float],
        line_height: float | None = None,
    ) -> float:
        """Measure if text fits in the given (x0, y0, x1, y1) rectangle.

        Args:
            text: Text content to test.
            font_name: Base-14 font code (e.g. helv, hebo, tiro).
            font_size: Font size in points.
            rect: Bounding box tuple (x0, y0, x1, y1).
            line_height: Optional line height factor.

        Returns:
            Float representing remaining vertical height in points if text fits (>= 0),
            or negative deficit (< 0) if text overflows.
        """
        shape = self._page.new_shape()
        r = pymupdf.Rect(*rect)
        # We do not call shape.commit(), keeping page empty and fast
        rc = shape.insert_textbox(
            r,
            text,
            fontname=font_name,
            fontsize=font_size,
            lineheight=line_height,
        )
        return float(rc)

    def close(self) -> None:
        """Close the underlying measurement document."""
        if hasattr(self, "_doc") and self._doc and not self._doc.is_closed:
            self._doc.close()

    def __enter__(self) -> "TextMeasurer":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
