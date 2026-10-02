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

from app.core.config import settings
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

    def _transcribe_gemini_sync(self, audio: bytes, language_code: str) -> str:
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            raise Exception("No GEMINI_API_KEY configured")
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        
        prompt = f"Please transcribe this meeting audio accurately. The language is {language_code}. Only return the transcribed text without any conversational formatting or markdown."
        response = model.generate_content([
            {"mime_type": "audio/wav", "data": audio},
            prompt
        ])
        return response.text.strip()

    async def _transcribe_groq(self, audio: bytes, filename: str, language_code: str) -> str:
        api_key = getattr(settings, "GROQ_API_KEY", None)
        if not api_key:
            raise Exception("No GROQ_API_KEY configured")
        
        # Groq expects a pure language code like 'en' or 'ml'
        clean_lang = language_code.split('-')[0]
        
        import httpx
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {api_key}"},
                files={"file": (filename, audio, "audio/wav")},
                data={"model": "whisper-large-v3", "language": clean_lang}
            )
            response.raise_for_status()
            return response.json().get("text", "").strip()

    async def transcribe_audio(
        self,
        audio: bytes,
        filename: str = "audio.wav",
        language_code: str = "ml-IN",
    ) -> Dict[str, Any]:
        if not audio:
            raise TranscriptionUnavailable("Empty audio payload.")
            
        # Map frontend logical language to API real language and mode
        mode = "monolingual"
        real_lang = "ml-IN"
        if language_code == "manglish":
            real_lang = "ml-IN"
            mode = "codemix"
        elif language_code == "hi":
            real_lang = "hi-IN"
        elif language_code == "en":
            real_lang = "en-IN"
        elif language_code == "ml":
            real_lang = "ml-IN"
        else:
            real_lang = language_code

        # --- 1. Primary: Sarvam Saaras ---
        try:
            result = await self.sarvam.transcribe(audio, filename=filename, language_code=real_lang, mode=mode)
            return {
                "transcript": (result.get("transcript") or "").strip(),
                "engine": "sarvam-saaras-v3",
                "language_code": result.get("language_code") or real_lang,
            }
        except Exception as e:
            logger.warning(f"Sarvam transcription failed, falling back to Gemini: {e}")

        # --- 2. Fallback 1: Gemini 1.5 Flash ---
        try:
            text = await asyncio.to_thread(self._transcribe_gemini_sync, audio, language_code)
            return {"transcript": text, "engine": "gemini-1.5-flash", "language_code": language_code}
        except Exception as e:
            logger.warning(f"Gemini transcription failed, falling back to Groq: {e}")

        # --- 3. Fallback 2: Groq Whisper Large v3 ---
        try:
            text = await self._transcribe_groq(audio, filename, language_code)
            return {"transcript": text, "engine": "groq-whisper-large-v3", "language_code": language_code}
        except Exception as e:
            logger.warning(f"Groq transcription failed, trying offline fallback: {e}")

        # --- 4. Offline fallback: wav2vec2 ---
        if not audio.startswith(_RIFF_HEADER):
            raise TranscriptionUnavailable(
                "All cloud engines (Sarvam, Gemini, Groq) failed. Offline wav2vec2 requires a 16 kHz mono WAV file, but the uploaded audio is not WAV."
            )

        try:
            text = await asyncio.to_thread(self.offline.transcribe, audio)
            return {"transcript": text, "engine": "wav2vec2-offline", "language_code": language_code}
        except Wav2Vec2Error as e:
            logger.warning(f"Offline transcription failed: {e}")
            raise TranscriptionUnavailable(f"All engines failed; last error: {e}") from e
