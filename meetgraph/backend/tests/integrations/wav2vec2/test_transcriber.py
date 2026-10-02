import io
import wave

import pytest

from app.integrations.wav2vec2.exceptions import TranscriberAudioError
from app.integrations.wav2vec2.transcriber import Wav2Vec2Transcriber


def _wav(seconds=1, rate=16000, channels=1):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = rate * seconds * channels
        w.writeframes(b"\x00\x00" * n)
    return buf.getvalue()


def test_decode_mono():
    samples, rate = Wav2Vec2Transcriber._decode_wav(_wav())
    assert rate == 16000
    assert len(samples) == 16000
    assert all(s == 0.0 for s in samples)


def test_decode_stereo_averaged():
    samples, rate = Wav2Vec2Transcriber._decode_wav(_wav(channels=2))
    assert rate == 16000
    assert len(samples) == 16000


def test_decode_rejects_non_wav():
    with pytest.raises(TranscriberAudioError):
        Wav2Vec2Transcriber._decode_wav(b"not audio")


def test_transcribe_rejects_wrong_rate():
    t = Wav2Vec2Transcriber()
    with pytest.raises(TranscriberAudioError):
        t.transcribe(_wav(rate=8000))


def test_transcribe_empty():
    with pytest.raises(TranscriberAudioError):
        Wav2Vec2Transcriber().transcribe(b"")
