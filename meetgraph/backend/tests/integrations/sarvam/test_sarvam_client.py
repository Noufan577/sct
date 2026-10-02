from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.integrations.sarvam.client import SarvamClient
from app.integrations.sarvam import exceptions as E


def _mock_http(response=None, side_effect=None):
    """Patch httpx.AsyncClient with an async-context-manager mock."""
    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=response, side_effect=side_effect)
    mock_cm = MagicMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_client)
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=mock_cm), mock_client


def _response(status=200, payload=None, text=""):
    r = MagicMock()
    r.status_code = status
    r.text = text
    r.json = MagicMock(return_value=payload or {})
    return r


@pytest.mark.asyncio
async def test_transcribe_success():
    payload = {"transcript": "hello", "language_code": "ml-IN"}
    patcher, mock_client = _mock_http(_response(200, payload))
    with patcher:
        result = await SarvamClient(api_key="k").transcribe(b"audio-bytes")
    assert result == payload
    _, kwargs = mock_client.post.call_args
    assert kwargs["headers"] == {"api-subscription-key": "k"}
    assert kwargs["data"]["model"] == "saaras:v3"
    assert kwargs["data"]["mode"] == "codemix"


@pytest.mark.asyncio
async def test_transcribe_auth_failure():
    patcher, _ = _mock_http(_response(403, text="forbidden"))
    with patcher:
        with pytest.raises(E.SarvamAuthenticationError):
            await SarvamClient(api_key="bad").transcribe(b"audio")


@pytest.mark.asyncio
async def test_transcribe_quota():
    patcher, _ = _mock_http(_response(429, text="slow down"))
    with patcher:
        with pytest.raises(E.SarvamQuotaError):
            await SarvamClient(api_key="k").transcribe(b"audio")


@pytest.mark.asyncio
async def test_transcribe_server_error():
    patcher, _ = _mock_http(_response(500, text="boom"))
    with patcher:
        with pytest.raises(E.SarvamApiError):
            await SarvamClient(api_key="k").transcribe(b"audio")


@pytest.mark.asyncio
async def test_transcribe_connection_error():
    patcher, _ = _mock_http(side_effect=httpx.ConnectError("down"))
    with patcher:
        with pytest.raises(E.SarvamConnectionError):
            await SarvamClient(api_key="k").transcribe(b"audio")


@pytest.mark.asyncio
async def test_transcribe_missing_key():
    with pytest.raises(E.SarvamAuthenticationError):
        await SarvamClient(api_key="").transcribe(b"audio")


@pytest.mark.asyncio
async def test_transcribe_empty_audio():
    with pytest.raises(E.SarvamClientError):
        await SarvamClient(api_key="k").transcribe(b"")
