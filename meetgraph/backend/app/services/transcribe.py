"""Transcription service: Sarvam primary, wav2vec2 offline fallback.

- Sarvam Saaras handles all common formats and code-mixed Malayalam.
- If Sarvam fails (no key, no network, quota), the local wav2vec2
  model is tried (16 kHz mono WAV only).
- If both fail, TranscriptionUnavailable is raised and the API
  answers 503 — never silent garbage.
- If the audio is not WAV-format and Sarvam is unavailable, a clear
  error is raised instead of silently trying wav2vec2 on non-WAV audio.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

# RIFF WAV header magic bytes (little-endian): "RIFF" followed by file size
_RIFF_HEADER = b"RIFF"

from app.integrations.sarvam.client import SarvamClient
from app.integrations.sarvam.exceptions import SarvamClientError
from app.integrations.wav2vec2.exceptions import Wav2Vec2Error
from app.integrations.wav2vec2.transcriber import Wav2Vec2Transcriber

logger = logging.getLogger(__name__)


class TranscriptionUnavailable(Exception):
    pass


class TranscribeService:
    def __init__(
        self,
        sarvam: Optional[SarvamClient] = None,
        offline: Optional[Wav2Vec2Transcriber] = None,
    ):
        self.sarvam = sarvam or SarvamClient()
        self.offline = offline or Wav2Vec2Transcriber()

    async def transcribe_audio(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        language_code: str = "ml-IN",
    ) -> Dict[str, Any]:
        if not audio:
            raise TranscriptionUnavailable("Empty audio payload.")

        # --- Primary: Sarvam Saaras ---
        try:
            result = await self.sarvam.transcribe(audio, filename=filename, language_code=language_code)
            return {
                "transcript": (result.get("transcript") or "").strip(),
                "engine": "sarvam-saaras-v3",
                "language_code": result.get("language_code") or language_code,
            }
        except SarvamClientError as e:
            logger.warning(f"Sarvam transcription failed, trying offline fallback: {e}")

        # --- Offline fallback: wav2vec2 ---
        # Only try wav2vec2 if the audio actually starts with a RIFF WAV header.
        # If it doesn't, skip the fallback and raise a clear error so the user
        # knows to upload a 16 kHz mono WAV or configure the Sarvam API key.
        if not audio.startswith(_RIFF_HEADER):
            raise TranscriptionUnavailable(
                "Offline wav2vec2 transcription requires a 16 kHz mono WAV file. "
                "The uploaded audio is not in WAV format, and Sarvam is unavailable. "
                "Please upload a WAV file or configure the SARVAM_API_KEY."
            )

        try:
            # CPU inference blocks the event loop — run in a thread.
            text = await asyncio.to_thread(self.offline.transcribe, audio)
            return {"transcript": text, "engine": "wav2vec2-offline", "language_code": language_code}
        except Wav2Vec2Error as e:
            logger.warning(f"Offline transcription failed: {e}")
            raise TranscriptionUnavailable(f"Both engines failed; last error: {e}") from e
