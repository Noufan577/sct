import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
from .exceptions import OllamaConnectionError, OllamaAPIError, OllamaClientError

class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None, timeout: float = 180.0):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model = model or settings.OLLAMA_MODEL
        # CPU inference with 4B models can exceed a minute on first load.
        self.timeout = timeout
        
    async def generate(self, prompt: str, system: Optional[str] = None, format: Optional[str] = None) -> Dict[str, Any]:
        """Generate a completion from Ollama."""
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            # Qwen3-style reasoning models: skip thinking tokens so the
            # response stays valid JSON and inference stays fast on CPU.
            # Other models ignore this field.
            "think": False,
            # Keep the model warm between demo requests (cold load ≈ 1 min on CPU).
            "keep_alive": "30m",
        }
        
        if system:
            payload["system"] = system
            
        if format:
            payload["format"] = format
            
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/generate", json=payload)
                response.raise_for_status()
                return response.json()
        except httpx.ConnectError as e:
            raise OllamaConnectionError(f"Failed to connect to Ollama at {self.base_url}") from e
        except httpx.HTTPStatusError as e:
            raise OllamaAPIError(f"Ollama API error: {e.response.status_code} - {e.response.text}") from e
        except Exception as e:
            raise OllamaClientError(f"Unexpected error communicating with Ollama: {str(e)}") from e
