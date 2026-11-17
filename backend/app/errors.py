"""Custom exceptions for the FC P&L Monitor pipeline and API."""


class IngestError(Exception):
    """Raised when an input file cannot be parsed into records at all."""


class AppError(Exception):
    """Base class for API-facing errors. Carries a stable error code + HTTP status."""

    code = "ERROR"
    status_code = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidFileError(AppError):
    code = "INVALID_FILE"
    status_code = 400


class NoDataError(AppError):
    code = "NO_DATA"
    status_code = 400


class NotFoundError(AppError):
    code = "NOT_FOUND"
    status_code = 404


class ProcessingError(AppError):
    code = "PROCESSING_ERROR"
    status_code = 500


class AlreadyProcessingError(AppError):
    code = "ALREADY_PROCESSING"
    status_code = 409
