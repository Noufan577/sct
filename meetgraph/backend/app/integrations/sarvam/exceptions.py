class SarvamClientError(Exception):
    """Base exception for Sarvam client errors."""
    pass


class SarvamConnectionError(SarvamClientError):
    """Raised when the Sarvam API is unreachable."""
    pass


class SarvamAuthenticationError(SarvamClientError):
    """Raised on 403 — invalid or missing API key."""
    pass


class SarvamQuotaError(SarvamClientError):
    """Raised on 429 — quota / rate limit exceeded."""
    pass


class SarvamApiError(SarvamClientError):
    """Raised for other API errors. Carries the HTTP status code."""

    def __init__(self, message: str, status_code=None):
        super().__init__(message)
        self.status_code = status_code
