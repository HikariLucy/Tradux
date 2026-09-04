"""Font classification, resolution, and safe Base-14 fallback mapping."""

import re

from pydantic import BaseModel, ConfigDict, Field


class ResolvedFont(BaseModel):
    """Resolved Base-14 font identifier and substitution metadata."""

    model_config = ConfigDict(frozen=True)

    font_name: str = Field(
        ..., description="Canonical Base-14 font name (e.g. helv, hebo, tiro)"
    )
    is_substitution: bool = Field(
        ...,
        description="True if a standard fallback was substituted for the original font",
    )
    family: str = Field(
        ..., description="Inferred font family: sans, serif, mono, symbol"
    )
    is_bold: bool = Field(..., description="Whether bold style was applied")
    is_italic: bool = Field(..., description="Whether italic/oblique style was applied")


# Exact standard PyMuPDF Base-14 names and aliases
BASE14_STANDARD_NAMES = {
    "helv",
    "hebo",
    "heit",
    "hebi",
    "helvetica",
    "helvetica-bold",
    "helvetica-oblique",
    "helvetica-boldoblique",
    "tiro",
    "tibo",
    "tiit",
    "tibi",
    "times-roman",
    "times-bold",
    "times-italic",
    "times-bolditalic",
    "cour",
    "cobo",
    "coit",
    "cobi",
    "courier",
    "courier-bold",
    "courier-oblique",
    "courier-boldoblique",
    "symb",
    "symbol",
    "zadb",
    "zapfdingbats",
}

# Regex to strip PDF subset prefixes like "BAAAAA+DINPro-Bold" -> "DINPro-Bold"
_SUBSET_PREFIX_RE = re.compile(r"^[A-Z]{6}\+(.+)$")

# Keyword patterns
_MONO_PATTERNS = (
    "mono",
    "courier",
    "consolas",
    "menlo",
    "monaco",
    "fixed",
    "terminal",
    "typewriter",
    "code",
)
_SERIF_PATTERNS = (
    "times",
    "serif",
    "roman",
    "georgia",
    "garamond",
    "palatino",
    "cambria",
    "baskerville",
    "minion",
    "caslon",
)
_SYMBOL_PATTERNS = ("symbol", "zapf", "dingbat", "wingding")
_BOLD_PATTERNS = ("bold", "black", "heavy", "semibold", "demi", "-bd", "_bd")
_ITALIC_PATTERNS = ("italic", "oblique", "slanted", "-it", "_it")


def clean_font_name(raw_name: str) -> str:
    """Strip subset prefix (e.g. ABCDEF+Arial -> Arial) and whitespace."""
    s = raw_name.strip()
    match = _SUBSET_PREFIX_RE.match(s)
    if match:
        return match.group(1).strip()
    return s


def resolve_font(
    font_name: str,
    is_bold: bool = False,
    is_italic: bool = False,
) -> ResolvedFont:
    """Resolve an extracted font name to a safe, deterministic Base-14 font.

    Args:
        font_name: Font name extracted from PDF span.
        is_bold: Optional bold hint from typographic flags.
        is_italic: Optional italic hint from typographic flags.

    Returns:
        ResolvedFont with standard Base-14 font code and metadata.
    """
    clean_name = clean_font_name(font_name)
    name_lower = clean_name.lower()

    # Detect bold/italic from name if not already set by flags
    effective_bold = is_bold or any(pat in name_lower for pat in _BOLD_PATTERNS)
    effective_italic = is_italic or any(pat in name_lower for pat in _ITALIC_PATTERNS)

    # Detect family
    if any(pat in name_lower for pat in _SYMBOL_PATTERNS):
        family = "symbol"
        resolved_name = (
            "zadb" if "zapf" in name_lower or "dingbat" in name_lower else "symb"
        )
    elif any(pat in name_lower for pat in _MONO_PATTERNS):
        family = "mono"
        if effective_bold and effective_italic:
            resolved_name = "cobi"
        elif effective_bold:
            resolved_name = "cobo"
        elif effective_italic:
            resolved_name = "coit"
        else:
            resolved_name = "cour"
    elif any(pat in name_lower for pat in _SERIF_PATTERNS):
        family = "serif"
        if effective_bold and effective_italic:
            resolved_name = "tibi"
        elif effective_bold:
            resolved_name = "tibo"
        elif effective_italic:
            resolved_name = "tiit"
        else:
            resolved_name = "tiro"
    else:
        # Default modern digital documents to sans-serif (Helvetica)
        family = "sans"
        if effective_bold and effective_italic:
            resolved_name = "hebi"
        elif effective_bold:
            resolved_name = "hebo"
        elif effective_italic:
            resolved_name = "heit"
        else:
            resolved_name = "helv"

    # Is it a substitution?
    is_sub = name_lower not in BASE14_STANDARD_NAMES

    return ResolvedFont(
        font_name=resolved_name,
        is_substitution=is_sub,
        family=family,
        is_bold=effective_bold,
        is_italic=effective_italic,
    )
