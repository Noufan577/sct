import pytest
from unittest.mock import AsyncMock, patch
import httpx
import json
import os

from app.integrations.meetily.client import MeetilyClient
from app.integrations.meetily.exceptions import (
    MeetilyConnectionError,
    MeetilyAuthenticationError,
    MeetilyNotFoundError,
    MeetilyApiError
)

# Fixture setup
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "../../../tests/fixtures/meetily")
try:
    with open(os.path.join(FIXTURE_DIR, "transcript_sample.json"), "r") as f:
        MOCK_TRANSCRIPT_SEGMENTS = json.load(f)
except FileNotFoundError:
    MOCK_TRANSCRIPT_SEGMENTS = [{"id": "1", "text": "hello"}]

@pytest.fixture
def client():
    return MeetilyClient(base_url="http://test", api_key="test-key")

@pytest.mark.asyncio
async def test_list_meetings_success(client):
    mock_response = httpx.Response(200, json={"meetings": [{"id": "m1"}], "total": 1})
    mock_response.request = httpx.Request("GET", "http://test")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        meetings = await client.list_meetings()
        
        assert len(meetings) == 1
        assert meetings[0]["id"] == "m1"
        mock_get.assert_called_once_with("/v1/meetings")

@pytest.mark.asyncio
async def test_get_transcript_success(client):
    mock_response = httpx.Response(200, json={
        "meeting_id": "m1",
        "title": "Test",
        "segments": MOCK_TRANSCRIPT_SEGMENTS
    })
    mock_response.request = httpx.Request("GET", "http://test")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        segments = await client.get_transcript("m1")
        
        assert len(segments) == len(MOCK_TRANSCRIPT_SEGMENTS)
        mock_get.assert_called_once_with("/v1/meetings/m1/transcript")

@pytest.mark.asyncio
async def test_auth_error(client):
    mock_response = httpx.Response(403, json={"error": "forbidden"})
    mock_response.request = httpx.Request("GET", "http://test")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with pytest.raises(MeetilyAuthenticationError):
            await client.list_meetings()

@pytest.mark.asyncio
async def test_not_found_error(client):
    mock_response = httpx.Response(404, json={"error": "not found"})
    mock_response.request = httpx.Request("GET", "http://test")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        
        with pytest.raises(MeetilyNotFoundError):
            await client.get_meeting("nonexistent")

@pytest.mark.asyncio
async def test_connection_error(client):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Connection failed")
        
        with pytest.raises(MeetilyConnectionError):
            await client.list_meetings()

@pytest.mark.asyncio
async def test_check_availability_success(client):
    mock_response = httpx.Response(200, json={"meetings": []})
    mock_response.request = httpx.Request("GET", "http://test")
    
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_response
        is_available = await client.check_availability()
        assert is_available is True

@pytest.mark.asyncio
async def test_check_availability_failure(client):
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.side_effect = httpx.ConnectError("Failed")
        is_available = await client.check_availability()
        assert is_available is False
