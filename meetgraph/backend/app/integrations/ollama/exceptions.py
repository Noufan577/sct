class OllamaClientError(Exception):
    """Base exception for Ollama client errors."""
    pass

class OllamaConnectionError(OllamaClientError):
    """Raised when the Ollama API is unreachable."""
    pass

class OllamaAPIError(OllamaClientError):
    """Raised when the Ollama API returns an error response."""
    pass
