"""Application-wide core exceptions."""


class TraduxError(Exception):
    """Base exception for all Tradux application errors."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class DocumentNotFoundError(TraduxError):
    """Raised when a requested document or file does not exist."""


class InvalidPDFError(TraduxError):
    """Raised when a file or stream is not a valid PDF or is corrupted."""


class EncryptedPDFError(TraduxError):
    """Raised when a PDF is password-protected or encrypted and cannot be opened."""


class EmptyDocumentError(TraduxError):
    """Raised when a document or stream is empty (0 bytes or contains no content)."""


class DocumentSizeExceededError(TraduxError):
    """Raised when an uploaded document exceeds the maximum permitted size."""


class TranslationError(TraduxError):
    """Base exception for errors occurring during document translation."""

    def __init__(
        self,
        message: str,
        page_number: int | None = None,
        reading_order: int | None = None,
    ) -> None:
        super().__init__(message)
        self.page_number = page_number
        self.reading_order = reading_order

    def __str__(self) -> str:
        loc = []
        if self.page_number is not None:
            loc.append(f"page={self.page_number}")
        if self.reading_order is not None:
            loc.append(f"block={self.reading_order}")
        if loc:
            return f"{self.message} ({', '.join(loc)})"
        return self.message


class TranslationIntegrityError(TranslationError):
    """Raised when token placeholders are missing, duplicated, or corrupted."""


class TranslationProviderError(TranslationError):
    """Raised when the translation provider fails (HTTP error, bad response, etc.)."""


class TranslationTimeoutError(TranslationError):
    """Raised when a translation provider request times out."""
