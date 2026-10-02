from unittest.mock import AsyncMock, MagicMock

import pytest

from app.integrations.sarvam.exceptions import SarvamConnectionError
from app.integrations.wav2vec2.exceptions import TranscriberUnavailable
from app.services.transcribe import TranscribeService, TranscriptionUnavailable


def _sarvam_ok(transcript="hello"):
    m = MagicMock()
    m.transcribe = AsyncMock(return_value={"transcript": transcript, "language_code": "ml-IN"})
    return m


def _sarvam_down():
    m = MagicMock()
    m.transcribe = AsyncMock(side_effect=SarvamConnectionError("down"))
    return m


def _offline_ok(text="offline words"):
    m = MagicMock()
    m.transcribe = MagicMock(return_value=text)
    return m


def _offline_down():
    m = MagicMock()
    m.transcribe = MagicMock(side_effect=TranscriberUnavailable("no torch"))
    return m


@pytest.mark.asyncio
async def test_sarvam_primary():
    svc = TranscribeService(sarvam=_sarvam_ok(), offline=_offline_down())
    result = await svc.transcribe_audio(b" heritage ")
    assert result == {"transcript": "hello", "engine": "sarvam-saaras-v3", "language_code": "ml-IN"}


@pytest.mark.asyncio
async def test_offline_fallback():
    svc = TranscribeService(sarvam=_sarvam_down(), offline=_offline_ok())
    result = await svc.transcribe_audio(b" heritage ")
    assert result["engine"] == "wav2vec2-offline"
    assert result["transcript"] == "offline words"


@pytest.mark.asyncio
async def test_both_fail():
    svc = TranscribeService(sarvam=_sarvam_down(), offline=_offline_down())
    with pytest.raises(TranscriptionUnavailable):
        await svc.transcribe_audio(b" heritage ")


@pytest.mark.asyncio
async def test_empty_audio():
    svc = TranscribeService(sarvam=_sarvam_ok(), offline=_offline_ok())
    with pytest.raises(TranscriptionUnavailable):
        await svc.transcribe_audio(b"")