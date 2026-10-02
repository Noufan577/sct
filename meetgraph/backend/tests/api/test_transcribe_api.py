"""API tests for Phase 7: POST /api/transcribe."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.api.routes.transcribe import get_transcribe_service
from app.services.transcribe import TranscriptionUnavailable

client = TestClient(app)

WAV = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"\x80>\x00\x00\x00}\x00\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


@pytest.fixture(autouse=True)
def mock_service():
    svc = MagicMock()
    svc.transcribe_audio = AsyncMock(return_value={
        "transcript": "budget report",
        "engine": "sarvam-saaras-v3",
        "language_code": "ml-IN",
    })
    app.dependency_overrides[get_transcribe_service] = lambda: svc
    yield svc
    app.dependency_overrides.pop(get_transcribe_service, None)


def test_transcribe_success():
    response = client.post(
        "/api/transcribe", files={"file": ("m.wav", WAV, "audio/wav")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["transcript"] == "budget report"
    assert data["engine"] == "sarvam-saaras-v3"


def test_transcribe_empty_file():
    response = client.post(
        "/api/transcribe", files={"file": ("m.wav", b"", "audio/wav")}
    )
    assert response.status_code == 422


def test_transcribe_unavailable(mock_service):
    mock_service.transcribe_audio = AsyncMock(
        side_effect=TranscriptionUnavailable("both engines failed")
    )
    response = client.post(
        "/api/transcribe", files={"file": ("m.wav", WAV, "audio/wav")}
    )
    assert response.status_code == 503
