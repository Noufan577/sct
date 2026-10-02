import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from app.main import app
from app.api.routes.meetings import get_meetily_service
from app.integrations.meetily.exceptions import (
    MeetilyNotFoundError,
    MeetilyAuthenticationError,
    MeetilyConnectionError,
    MeetilyClientError
)

client = TestClient(app)

class MockMeetilyService:
    async def list_meetings(self):
        return [{"id": "m1", "title": "Test Meeting"}]
        
    async def get_meeting(self, meeting_id: str):
        if meeting_id == "notfound":
            raise MeetilyNotFoundError("Not found")
        if meeting_id == "unauth":
            raise MeetilyAuthenticationError("Auth error")
        if meeting_id == "connerr":
            raise MeetilyConnectionError("Connection error")
        if meeting_id == "apierr":
            raise MeetilyClientError("API error")
        return {"id": meeting_id, "title": "Test"}
        
    async def get_transcript(self, meeting_id: str):
        return [{"id": "s1", "text": "hello"}]

app.dependency_overrides[get_meetily_service] = MockMeetilyService

def test_list_meetings():
    response = client.get("/api/meetily/meetings")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_meeting_success():
    response = client.get("/api/meetily/meetings/m1")
    assert response.status_code == 200
    assert response.json()["id"] == "m1"

def test_get_transcript_success():
    response = client.get("/api/meetily/meetings/m1/transcript")
    assert response.status_code == 200
    assert len(response.json()) == 1

def test_get_meeting_not_found():
    response = client.get("/api/meetily/meetings/notfound")
    assert response.status_code == 404
    
def test_get_meeting_unauth():
    response = client.get("/api/meetily/meetings/unauth")
    assert response.status_code == 401
    
def test_get_meeting_connerr():
    response = client.get("/api/meetily/meetings/connerr")
    assert response.status_code == 502
    
def test_get_meeting_apierr():
    response = client.get("/api/meetily/meetings/apierr")
    assert response.status_code == 500
