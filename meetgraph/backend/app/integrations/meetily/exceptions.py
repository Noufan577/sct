class MeetilyClientError(Exception):
    """Base exception for all Meetily client errors."""
    pass

class MeetilyConnectionError(MeetilyClientError):
    """Raised when unable to connect to the Meetily API."""
    pass

class MeetilyAuthenticationError(MeetilyClientError):
    """Raised when authentication with Meetily API fails."""
    pass

class MeetilyNotFoundError(MeetilyClientError):
    """Raised when a requested resource is not found (404)."""
    pass

class MeetilyApiError(MeetilyClientError):
    """Raised for other API HTTP errors."""
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code
