class Wav2Vec2Error(Exception):
    """Base exception for the offline transcriber."""
    pass


class TranscriberUnavailable(Wav2Vec2Error):
    """Raised when torch/transformers or the model cannot be loaded."""
    pass


class TranscriberAudioError(Wav2Vec2Error):
    """Raised when the audio cannot be decoded (expects 16 kHz mono WAV)."""
    pass
