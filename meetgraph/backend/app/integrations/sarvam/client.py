"""Sarvam Saaras speech-to-text client (Phase 7).

REST reference: POST https://api.sarvam.ai/speech-to-text (multipart).
Auth: `api-subscription-key` header. Auth failures come back as 403.
Model `saaras:v3` with mode `codemix` is used for code-mixed
Malayalam/English (Manglish) meeting audio.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.core.config import settings
from app.integrations.sarvam.exceptions import (
    SarvamApiError,
    SarvamAuthenticationError,
    SarvamClientError,
    SarvamConnectionError,
    SarvamQuotaError,
)

logger = logging.getLogger(__name__)


class SarvamClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 60.0,
    ):
        self.base_url = (base_url or settings.SARVAM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.SARVAM_API_KEY
        self.model = model or settings.SARVAM_MODEL
        self.timeout = timeout

    async def transcribe(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        language_code: str = "ml-IN",
        mode: str = "codemix",
        with_timestamps: bool = True,
    ) -> Dict[str, Any]:
        """Transcribe audio bytes. Returns the raw Sarvam response dict
        (transcript, language_code, timestamps, ...)."""
        if not self.api_key:
            raise SarvamAuthenticationError("Sarvam API key is not configured.")
        if not audio:
            raise SarvamClientError("Empty audio payload.")

        files = {"file": (filename, audio, "audio/wav")}
        data = {
            "model": self.model,
            "mode": mode,
            "language_code": language_code,
            "with_timestamps": "true" if with_timestamps else "false",
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/speech-to-text",
                    headers={"api-subscription-key": self.api_key},
                    files=files,
                    data=data,
                )
        except httpx.RequestError as e:
            raise SarvamConnectionError(f"Connection failed: {e}") from e

        if response.status_code == 403:
            raise SarvamAuthenticationError(f"Invalid Sarvam API key: {response.text}")
        if response.status_code == 429:
            raise SarvamQuotaError(f"Sarvam quota exceeded: {response.text}")
        if response.status_code >= 400:
            raise SarvamApiError(
                f"Sarvam API error ({response.status_code}): {response.text}",
                status_code=response.status_code,
            )
        try:
            return response.json()
        except ValueError as e:
            raise SarvamApiError(f"Invalid JSON in Sarvam response: {response.text}") from e
