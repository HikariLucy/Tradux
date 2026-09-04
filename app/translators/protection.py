"""Protection layer to mask and restore sensitive and non-translatable tokens."""

import re

from app.core.errors import TranslationIntegrityError

# Precompiled regex patterns for automatic token protection
URL_PATTERN = re.compile(r'https?://[^\s<>"{}|\\^`]+')
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
IPV4_PATTERN = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}"
    r"(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b"
)
MAC_PATTERN = re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b")
CODE_PATTERN = re.compile(r"\b[A-Z0-9]+(?:[-_][A-Z0-9]+)+\b")
NUMBER_PATTERN = re.compile(r"\b\d+(?:[.,]\d+)?\b")

PLACEHOLDER_PREFIX = "__TRX_PH_"
PLACEHOLDER_REGEX = re.compile(r"__TRX_PH_\d+__")


def mask_protected_tokens(
    text: str,
    protected_terms: list[str] | None = None,
) -> tuple[str, dict[str, str]]:
    """Mask sensitive tokens and protected terms with deterministic placeholders.

    Args:
        text: Source text to protect.
        protected_terms: Optional list of verbatim terms that must not be translated.

    Returns:
        tuple of (masked_text, token_map) where token_map maps
        placeholder -> original value.
    """
    if not text:
        return text, {}

    matches: list[tuple[int, int, str]] = []

    # 1. Explicit protected terms (highest priority, sorted by length descending)
    if protected_terms:
        unique_terms = sorted(
            [t for t in set(protected_terms) if t.strip()],
            key=len,
            reverse=True,
        )
        for term in unique_terms:
            pattern = re.compile(re.escape(term))
            for m in pattern.finditer(text):
                matches.append((m.start(), m.end(), m.group(0)))

    # 2. Structural patterns and reserved Tradux placeholders
    for pat in (
        PLACEHOLDER_REGEX,
        URL_PATTERN,
        EMAIL_PATTERN,
        IPV4_PATTERN,
        MAC_PATTERN,
        CODE_PATTERN,
        NUMBER_PATTERN,
    ):
        for m in pat.finditer(text):
            matches.append((m.start(), m.end(), m.group(0)))

    if not matches:
        return text, {}

    # Detect any existing placeholders in the source text to prevent collisions
    existing_placeholders = set(PLACEHOLDER_REGEX.findall(text))
    existing_ids: set[int] = set()
    for ph in existing_placeholders:
        try:
            # Extract number from __TRX_PH_{index}__
            num_part = ph[len(PLACEHOLDER_PREFIX) : -2]
            existing_ids.add(int(num_part))
        except ValueError:
            pass

    # Sort matches: earlier start position first; if tied, longer match first
    matches.sort(key=lambda item: (item[0], -(item[1] - item[0])))

    # Filter overlapping matches (first non-overlapping wins)
    non_overlapping: list[tuple[int, int, str]] = []
    last_end = 0
    for start, end, val in matches:
        if start >= last_end:
            non_overlapping.append((start, end, val))
            last_end = end

    # Construct masked text and token mapping using available indices
    token_map: dict[str, str] = {}
    builder: list[str] = []
    current_idx = 0
    next_id = 0

    for start, end, original_val in non_overlapping:
        # Find next available index that does not collide with source text
        while next_id in existing_ids:
            next_id += 1

        builder.append(text[current_idx:start])
        placeholder = f"{PLACEHOLDER_PREFIX}{next_id:03d}__"
        existing_ids.add(next_id)
        next_id += 1

        builder.append(placeholder)
        token_map[placeholder] = original_val
        current_idx = end

    # Append remaining trailing text
    builder.append(text[current_idx:])
    masked_text = "".join(builder)
    return masked_text, token_map


def restore_protected_tokens(
    translated_text: str,
    token_map: dict[str, str],
    source_text: str | None = None,
    page_number: int | None = None,
    reading_order: int | None = None,
) -> str:
    """Restore placeholders in translated text back to their original values.

    Validates that each placeholder appears exactly once and that no corrupted
    or orphan placeholders remain.

    Args:
        translated_text: Text containing placeholders returned by translator.
        token_map: Mapping of placeholder -> original value.
        source_text: Optional original source text to allow pre-existing tokens.
        page_number: Optional page number for error localization.
        reading_order: Optional block reading order for error localization.

    Returns:
        Restored text with original tokens in place.

    Raises:
        TranslationIntegrityError: If any placeholder is missing, duplicated,
            or corrupted.
    """
    # 1. Check for unexpected or corrupted placeholders in translated text
    translated_placeholders = PLACEHOLDER_REGEX.findall(translated_text)
    unexpected = [ph for ph in translated_placeholders if ph not in token_map]
    if unexpected:
        raise TranslationIntegrityError(
            f"Unexpected or corrupted placeholder(s) in translation: {unexpected}",
            page_number=page_number,
            reading_order=reading_order,
        )

    result = translated_text

    # 2. Check presence and uniqueness of each placeholder, and restore
    for placeholder, original_value in token_map.items():
        count = result.count(placeholder)
        if count == 0:
            raise TranslationIntegrityError(
                f"Missing protected placeholder '{placeholder}' in translation",
                page_number=page_number,
                reading_order=reading_order,
            )
        if count > 1:
            raise TranslationIntegrityError(
                f"Duplicated protected placeholder '{placeholder}' (count={count})",
                page_number=page_number,
                reading_order=reading_order,
            )
        result = result.replace(placeholder, original_value)

    # 3. Verify remaining placeholders in result were legitimate original values
    source_placeholders = (
        set(PLACEHOLDER_REGEX.findall(source_text))
        if source_text is not None
        else {v for v in token_map.values() if PLACEHOLDER_REGEX.fullmatch(v)}
    )
    remaining = [
        ph for ph in PLACEHOLDER_REGEX.findall(result) if ph not in source_placeholders
    ]
    if remaining:
        raise TranslationIntegrityError(
            f"Unexpected or corrupted placeholder(s) in translation: {remaining}",
            page_number=page_number,
            reading_order=reading_order,
        )

    return result
