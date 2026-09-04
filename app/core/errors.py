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
