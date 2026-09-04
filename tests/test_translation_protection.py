"""Unit tests for the token protection and restoration layer."""

import pytest

from app.core.errors import TranslationIntegrityError
from app.translators.protection import (
    mask_protected_tokens,
    restore_protected_tokens,
)


def test_mask_and_restore_protected_terms() -> None:
    """Verify explicit protected terms are masked and restored verbatim."""
    text = "The quick Tradux engine translates Micron manuals with HighAccuracy."
    protected = ["Tradux", "Micron", "HighAccuracy"]

    masked, token_map = mask_protected_tokens(text, protected_terms=protected)

    assert "Tradux" not in masked
    assert "Micron" not in masked
    assert "HighAccuracy" not in masked
    assert len(token_map) == 3

    # Simulate translation preserving placeholders
    translated_synthetic = (
        f"[ES] El motor {list(token_map.keys())[0]} traduce manuales "
        f"{list(token_map.keys())[1]} con {list(token_map.keys())[2]}."
    )

    restored = restore_protected_tokens(translated_synthetic, token_map)
    assert "Tradux" in restored
    assert "Micron" in restored
    assert "HighAccuracy" in restored
    assert "__TRX_PH_" not in restored


def test_mask_urls_emails_ips_and_macs() -> None:
    """Verify URLs, emails, IPv4, and MAC addresses are protected."""
    text = (
        "Contact dev@tradux.io or visit https://tradux.io/docs at 192.168.1.100 "
        "interface 00:1A:2B:3C:4D:5E."
    )

    masked, token_map = mask_protected_tokens(text)

    assert "dev@tradux.io" not in masked
    assert "https://tradux.io/docs" not in masked
    assert "192.168.1.100" not in masked
    assert "00:1A:2B:3C:4D:5E" not in masked

    values = set(token_map.values())
    assert "dev@tradux.io" in values
    assert "https://tradux.io/docs" in values
    assert "192.168.1.100" in values
    assert "00:1A:2B:3C:4D:5E" in values

    # Invert/simulate translation
    translated = f"Texto traducido: {masked}"
    restored = restore_protected_tokens(translated, token_map)

    assert "dev@tradux.io" in restored
    assert "https://tradux.io/docs" in restored
    assert "192.168.1.100" in restored
    assert "00:1A:2B:3C:4D:5E" in restored


def test_mask_technical_codes_and_numbers() -> None:
    """Verify technical codes and standalone numbers are masked."""
    text = "Model MODEL-X100 complies with ISO-9001 and has 42 units at 99.5 percent."

    masked, token_map = mask_protected_tokens(text)

    assert "MODEL-X100" not in masked
    assert "ISO-9001" not in masked
    assert "42" not in masked
    assert "99.5" not in masked

    values = set(token_map.values())
    assert "MODEL-X100" in values
    assert "ISO-9001" in values
    assert "42" in values
    assert "99.5" in values

    restored = restore_protected_tokens(f"[FR] {masked}", token_map)
    assert "MODEL-X100" in restored
    assert "ISO-9001" in restored
    assert "42" in restored
    assert "99.5" in restored


def test_repeated_terms_produce_distinct_placeholders() -> None:
    """Verify identical terms appearing multiple times receive distinct placeholders."""
    text = "Tradux is fast because Tradux is modular."
    masked, token_map = mask_protected_tokens(text, protected_terms=["Tradux"])

    # Two distinct placeholder keys
    assert len(token_map) == 2
    keys = list(token_map.keys())
    assert keys[0] != keys[1]
    assert token_map[keys[0]] == "Tradux"
    assert token_map[keys[1]] == "Tradux"

    # Restoring handles both independently
    translated = f"{keys[0]} est rapide parce que {keys[1]} est modulaire."
    restored = restore_protected_tokens(translated, token_map)
    assert restored == "Tradux est rapide parce que Tradux est modulaire."


def test_missing_placeholder_raises_integrity_error() -> None:
    """Verify missing placeholder raises TranslationIntegrityError with location."""
    text = "Protect MODEL-100 here."
    _, token_map = mask_protected_tokens(text)

    corrupted_translation = "The model was removed completely."
    with pytest.raises(
        TranslationIntegrityError, match="Missing protected placeholder"
    ) as exc_info:
        restore_protected_tokens(
            corrupted_translation,
            token_map,
            page_number=2,
            reading_order=5,
        )

    assert exc_info.value.page_number == 2
    assert exc_info.value.reading_order == 5
    assert "page=2, block=5" in str(exc_info.value)


def test_duplicated_placeholder_raises_integrity_error() -> None:
    """Verify duplicated placeholder raises TranslationIntegrityError."""
    text = "System SERIAL-999 initialized."
    _, token_map = mask_protected_tokens(text)
    ph = list(token_map.keys())[0]

    duplicated_translation = f"System {ph} and duplicate {ph}."
    with pytest.raises(
        TranslationIntegrityError, match="Duplicated protected placeholder"
    ) as exc:
        restore_protected_tokens(duplicated_translation, token_map)

    assert "count=2" in str(exc.value)


def test_corrupted_orphan_placeholder_raises_integrity_error() -> None:
    """Verify extra orphan placeholder raises TranslationIntegrityError."""
    text = "Normal text without special tokens."
    _, token_map = mask_protected_tokens(text)

    hallucinated_translation = "Translated text with hallucinated __TRX_PH_999__."
    with pytest.raises(TranslationIntegrityError, match="corrupted placeholder"):
        restore_protected_tokens(hallucinated_translation, token_map)


def test_placeholder_collision_with_source_text() -> None:
    """Verify source text with __TRX_PH_000__ is masked with a new index."""
    text = "Error code __TRX_PH_000__ detected in endpoint https://tradux.dev"
    masked, token_map = mask_protected_tokens(text)

    # 1. Existing __TRX_PH_000__ is masked using a non-colliding index
    assert "__TRX_PH_000__" not in masked
    assert "__TRX_PH_001__" in masked
    assert "https://tradux.dev" not in masked
    assert "__TRX_PH_002__" in masked

    # 2. Token map maps generated placeholders to source content
    assert token_map["__TRX_PH_001__"] == "__TRX_PH_000__"
    assert token_map["__TRX_PH_002__"] == "https://tradux.dev"

    # 3. Restoration preserves both the original __TRX_PH_000__ and restored URL
    synthetic_translated = f"[ES] {masked}"
    restored = restore_protected_tokens(
        synthetic_translated, token_map, source_text=text
    )
    expected = "[ES] Error code __TRX_PH_000__ detected in endpoint https://tradux.dev"
    assert restored == expected


def test_preexisting_single_placeholder_masked_and_restored() -> None:
    """Requirement 1: Verify source text with __TRX_PH_000__ is masked and restored."""
    text = "Error __TRX_PH_000__ MODEL-X100"
    masked, token_map = mask_protected_tokens(text)

    # Generated placeholders avoid existing ID 000
    assert masked == "Error __TRX_PH_001__ __TRX_PH_002__"
    assert token_map == {
        "__TRX_PH_001__": "__TRX_PH_000__",
        "__TRX_PH_002__": "MODEL-X100",
    }

    # Restores verbatim
    restored = restore_protected_tokens(f"[ES] {masked}", token_map, source_text=text)
    assert restored == f"[ES] {text}"


def test_preexisting_multiple_placeholders_with_codes_and_numbers() -> None:
    """Requirements 2, 3, 4: Verify multiple pre-existing placeholders
    (__TRX_PH_000__, __TRX_PH_001__, __TRX_PH_999__), technical codes
    (MODEL-X100), and protectable numbers are masked and restored verbatim.
    """
    text = (
        "Tokens __TRX_PH_000__, __TRX_PH_001__, and __TRX_PH_999__ on "
        "MODEL-X100 with 42 units at 99.5 percent."
    )
    masked, token_map = mask_protected_tokens(text)

    # 1. Verify none of the source tokens appear in masked text
    assert "__TRX_PH_000__" not in masked
    assert "__TRX_PH_001__" not in masked
    assert "__TRX_PH_999__" not in masked
    assert "MODEL-X100" not in masked
    assert "42" not in masked
    assert "99.5" not in masked

    # 2. Generated indices avoid all IDs existing in source text (0, 1, 999)
    for placeholder_key in token_map:
        num = int(placeholder_key.replace("__TRX_PH_", "").replace("__", ""))
        assert num not in {0, 1, 999}

    # 3. All tokens are properly mapped
    values = set(token_map.values())
    assert "__TRX_PH_000__" in values
    assert "__TRX_PH_001__" in values
    assert "__TRX_PH_999__" in values
    assert "MODEL-X100" in values
    assert "42" in values
    assert "99.5" in values

    # 4. All tokens are restored exactly verbatim
    translated_synthetic = f"[ES] {masked}"
    restored = restore_protected_tokens(
        translated_synthetic, token_map, source_text=text
    )
    assert restored == f"[ES] {text}"


def test_preexisting_placeholder_integrity_error_on_provider_tampering() -> None:
    """Requirement 5: Verify TranslationIntegrityError is raised when provider
    deletes, duplicates, or corrupts the generated placeholder.
    """
    text = "Error __TRX_PH_000__ MODEL-X100"
    masked, token_map = mask_protected_tokens(text)
    ph_for_source = "__TRX_PH_001__"

    # Case A: Provider eliminates generated placeholder protecting source token
    eliminated = masked.replace(ph_for_source, "")
    with pytest.raises(
        TranslationIntegrityError, match="Missing protected placeholder"
    ):
        restore_protected_tokens(eliminated, token_map, source_text=text)

    # Case B: Provider duplicates generated placeholder protecting source token
    duplicated = f"{masked} {ph_for_source}"
    with pytest.raises(
        TranslationIntegrityError, match="Duplicated protected placeholder"
    ):
        restore_protected_tokens(duplicated, token_map, source_text=text)

    # Case C: Provider corrupts placeholder syntax (e.g. broken suffix)
    corrupted_syntax = masked.replace(ph_for_source, "__TRX_PH_001_")
    with pytest.raises(
        TranslationIntegrityError, match="Missing protected placeholder"
    ):
        restore_protected_tokens(corrupted_syntax, token_map, source_text=text)

    # Case D: Provider corrupts generated placeholder to unexpected ID
    corrupted_id = masked.replace(ph_for_source, "__TRX_PH_777__")
    with pytest.raises(TranslationIntegrityError, match="corrupted placeholder"):
        restore_protected_tokens(corrupted_id, token_map, source_text=text)

    # Case E: Provider prematurely unmasks to original source token __TRX_PH_000__
    premature_unmask = masked.replace(ph_for_source, "__TRX_PH_000__")
    with pytest.raises(TranslationIntegrityError, match="corrupted placeholder"):
        restore_protected_tokens(premature_unmask, token_map, source_text=text)


def test_preexisting_placeholder_masking_determinism() -> None:
    """Requirement 6: Verify two executions on the exact same input produce
    identical masked text, token maps, and restored output.
    """
    text = "Check __TRX_PH_000__, __TRX_PH_001__, __TRX_PH_999__, MODEL-X100, and 42."
    masked1, token_map1 = mask_protected_tokens(text)
    masked2, token_map2 = mask_protected_tokens(text)

    assert masked1 == masked2
    assert token_map1 == token_map2

    restored1 = restore_protected_tokens(
        f"[ES] {masked1}", token_map1, source_text=text
    )
    restored2 = restore_protected_tokens(
        f"[ES] {masked2}", token_map2, source_text=text
    )

    assert restored1 == restored2
    assert restored1 == f"[ES] {text}"


def test_protected_terms_literal_overlapping_and_special_chars() -> None:
    """Verify literal protection, precedence, and special regex characters."""
    protected = ["MODEL", "MODEL-X100", "C++", "A.B"]
    text = "In C++, MODEL-X100 and MODEL tested on A.B. Repeat: MODEL-X100 and C++."

    masked, token_map = mask_protected_tokens(text, protected_terms=protected)

    # All terms must be masked
    assert "MODEL-X100" not in masked
    assert "MODEL" not in masked
    assert "C++" not in masked
    assert "A.B" not in masked

    # Distinct placeholders for repeated terms
    assert len(token_map) == 6
    values = list(token_map.values())
    assert values.count("MODEL-X100") == 2
    assert values.count("MODEL") == 1
    assert values.count("C++") == 2
    assert values.count("A.B") == 1

    # Restoration recovers the exact verbatim text
    restored = restore_protected_tokens(f"[FR] {masked}", token_map, source_text=text)
    assert restored == f"[FR] {text}"
