"""API tests for Meetily sync: status flags + one-meeting import."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import get_db, Base
from app.db.models import MeetingModel
from app.api.routes.meetings import get_meetily_service
from app.api.routes.query import get_ollama_client
from app.integrations.meetily.exceptions import MeetilyNotFoundError

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


def make_meetily(meetings):
    svc = MagicMock()
    svc.list_meetings = AsyncMock(return_value=meetings)

    async def _get_meeting(mid):
        for m in meetings:
            if m["id"] == mid:
                return m
        raise MeetilyNotFoundError("nope")

    svc.get_meeting = AsyncMock(side_effect=_get_meeting)
    svc.get_transcript = AsyncMock(return_value=[
        {"id": "s1", "speaker": "Alice", "text": "I will finish the report by Friday."}
    ])
    return svc


def make_ollama():
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({"commitments": [
            {"segment_id": "s1", "person": "Alice", "commitment": "Finish the report", "deadline": "Friday"}
        ]})
    })
    return mock


MEETINGS = [
    {"id": "m1", "title": "Old meeting"},
    {"id": "m2", "title": "New meeting"},
]

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_meetily_service] = lambda: make_meetily(MEETINGS)
    app.dependency_overrides[get_ollama_client] = make_ollama
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add(MeetingModel(meetily_id="m1", title="Old meeting"))
    db.commit()
    db.close()
    yield
    for dep in (get_db, get_meetily_service, get_ollama_client):
        app.dependency_overrides.pop(dep, None)


def test_sync_status_flags():
    response = client.get("/api/sync/status")
    assert response.status_code == 200
    data = {m["id"]: m for m in response.json()}
    assert data["m1"]["fetched"] is True
    assert data["m2"]["fetched"] is False


def test_import_unfetched_meeting():
    response = client.post("/api/sync/meetings/m2")
    assert response.status_code == 200
    assert response.json()["commitments_found"] == 1

    status = client.get("/api/sync/status").json()
    assert {m["id"]: m["fetched"] for m in status} == {"m1": True, "m2": True}

    detail = client.get("/api/meetings/m2").json()
    assert detail["commitments"][0]["person"] == "Alice"


def test_import_missing_meeting():
    response = client.post("/api/sync/meetings/nope")
    assert response.status_code == 404
