"""Offline wav2vec2 fallback transcriber (Phase 7).

Fully local: no API key, no network at inference time (model is
downloaded once from Hugging Face on first use). Heavy: torch +
transformers plus a ~360 MB model, CPU inference is slow — this is
the fallback when Sarvam is unreachable, not the primary engine.

Input contract (kept dependency-free on purpose): 16-bit mono WAV.
Anything else raises TranscriberAudioError — in practice the Sarvam
primary path accepts all common formats.

All heavy imports are lazy so the rest of the app (and tests) work
without torch installed.
"""

import io
import logging
import wave

from app.core.config import settings
from app.integrations.wav2vec2.exceptions import (
    TranscriberAudioError,
    TranscriberUnavailable,
)

logger = logging.getLogger(__name__)


class Wav2Vec2Transcriber:
    def __init__(self, model: str = None):
        self.model = model or settings.WAV2VEC2_MODEL
        self._pipe = None

    def _load(self):
        if self._pipe is not None:
            return self._pipe
        try:
            from transformers import pipeline
        except ImportError as e:
            raise TranscriberUnavailable(
                "transformers/torch are not installed. "
                "Install with: pip install torch transformers"
            ) from e
        try:
            self._pipe = pipeline("automatic-speech-recognition", model=self.model)
        except Exception as e:
            raise TranscriberUnavailable(f"Could not load model {self.model}: {e}") from e
        return self._pipe

    @staticmethod
    def _decode_wav(audio: bytes):
        """Decode WAV bytes to (samples float32 list, sample_rate)."""
        try:
            with wave.open(io.BytesIO(audio), "rb") as w:
                n_channels, sampwidth, framerate, n_frames = w.getparams()[:4]
                frames = w.readframes(n_frames)
        except Exception as e:
            raise TranscriberAudioError(f"Not a readable WAV file: {e}") from e
        if sampwidth != 2:
            raise TranscriberAudioError("Only 16-bit WAV is supported.")
        import array

        samples = array.array("h", frames)
        if n_channels == 2:
            left = samples[0::2]
            right = samples[1::2]
            samples = array.array("h", (int((a + b) / 2) for a, b in zip(left, right)))
        elif n_channels != 1:
            raise TranscriberAudioError("Only mono/stereo WAV is supported.")
        floats = [s / 32768.0 for s in samples]
        return floats, framerate

    def transcribe(self, audio: bytes) -> str:
        """Transcribe 16 kHz mono WAV bytes. Returns plain text."""
        if not audio:
            raise TranscriberAudioError("Empty audio payload.")
        samples, sample_rate = self._decode_wav(audio)
        if sample_rate != 16000:
            raise TranscriberAudioError(
                f"Only 16 kHz WAV is supported, got {sample_rate} Hz."
            )
        pipe = self._load()
        try:
            import numpy as np

            model_input = np.array(samples, dtype=np.float32)
        except ImportError:
            try:
                import torch

                model_input = torch.tensor(samples, dtype=torch.float32)
            except ImportError as e:
                raise TranscriberUnavailable(
                    "Neither numpy nor torch is available for model input."
                ) from e
        result = pipe({"array": model_input, "sampling_rate": sample_rate})
        text = result.get("text", "") if isinstance(result, dict) else ""
        return text.strip()
