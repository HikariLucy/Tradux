"""Color normalization utilities for document extraction."""


def normalize_color_to_hex(color_value: int | tuple[float, ...] | None) -> str:
    """Normalize a color value from PyMuPDF to a canonical uppercase #RRGGBB hex string.

    PyMuPDF span dictionaries represent RGB colors as an sRGB 24-bit integer:
    (r << 16) + (g << 8) + b.

    Args:
        color_value: Integer representation from PyMuPDF, or tuple of
            floats/ints, or None.

    Returns:
        Canonical uppercase hex string, e.g. '#000000', '#FF0000'.
    """
    if color_value is None:
        return "#000000"

    if isinstance(color_value, int):
        # Handle 24-bit sRGB integer
        color_int = max(0, color_value)
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return f"#{r:02X}{g:02X}{b:02X}"

    if isinstance(color_value, (tuple, list)):
        if len(color_value) >= 3:
            # Check if values are 0.0-1.0 floats or 0-255 ints
            c = [
                int(round(x * 255))
                if isinstance(x, float) and 0.0 <= x <= 1.0
                else int(x)
                for x in color_value[:3]
            ]
            r, g, b = [min(255, max(0, val)) for val in c]
            return f"#{r:02X}{g:02X}{b:02X}"

    return "#000000"
