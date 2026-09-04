"""Color conversion utilities for PDF rendering."""

import re

_HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def hex_to_rgb_float(hex_color: str) -> tuple[float, float, float]:
    """Convert a #RRGGBB hex color string to an RGB float tuple in [0.0, 1.0].

    If the string is invalid or cannot be parsed, falls back safely
    to black (0.0, 0.0, 0.0).

    Args:
        hex_color: Color string like '#1864AB' or '000000'.

    Returns:
        Tuple of (r, g, b) floats between 0.0 and 1.0.
    """
    clean = hex_color.strip()
    match = _HEX_COLOR_RE.match(clean)
    if not match:
        return (0.0, 0.0, 0.0)

    raw_hex = match.group(1)
    r = int(raw_hex[0:2], 16) / 255.0
    g = int(raw_hex[2:4], 16) / 255.0
    b = int(raw_hex[4:6], 16) / 255.0
    return (round(r, 4), round(g, 4), round(b, 4))
