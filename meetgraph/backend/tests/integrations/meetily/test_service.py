import pytest
from unittest.mock import AsyncMock, MagicMock
from app.integrations.meetily.service import MeetilyService

@pytest.fixture
def mock_client():
    client = MagicMock()
    client.list_meetings = AsyncMock(return_value=[{"id": "m1", "title": "Test"}])
    client.get_meeting = AsyncMock(return_value={"id": "m1", "title": "Test"})
    client.get_transcript = AsyncMock(return_value=[{"id": "s1", "text": "hello"}])
    return client

@pytest.fixture
def service(mock_client):
    return MeetilyService(client=mock_client)

@pytest.mark.asyncio
async def test_list_meetings(service, mock_client):
    result = await service.list_meetings()
    assert len(result) == 1
    assert result[0]["id"] == "m1"
    mock_client.list_meetings.assert_called_once()

@pytest.mark.asyncio
async def test_get_meeting(service, mock_client):
    result = await service.get_meeting("m1")
    assert result["id"] == "m1"
    mock_client.get_meeting.assert_called_once_with("m1")

@pytest.mark.asyncio
async def test_get_transcript(service, mock_client):
    result = await service.get_transcript("m1")
    assert len(result) == 1
    assert result[0]["text"] == "hello"
    mock_client.get_transcript.assert_called_once_with("m1")
