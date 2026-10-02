"""API tests for Phase 8: POST /api/recap."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import get_db, Base
from app.db.models import MeetingModel, CommitmentModel
from app.api.routes.query import get_ollama_client

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


def make_mock_ollama():
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({
            "recap": "Rahul budget report cheythu.",
            "action_items": ["Priya: book tickets"],
        })
    })
    return mock


client = TestClient(app)


def _seed():
    db = TestingSessionLocal()
    m = MeetingModel(meetily_id="demo-m1", title="Sprint planning")
    db.add(m)
    db.commit()
    db.refresh(m)
    for person, text, status in (
        ("Rahul", "Prepare the budget report", "COMPLETED"),
        ("Priya", "Book flight tickets", "OPEN"),
    ):
        db.add(CommitmentModel(
            meeting_id=m.id,
            person=person,
            commitment=text,
            status=status,
            evidence_segment_id="s1",
            evidence_speaker=person,
            evidence_timestamp=1.0,
            evidence_text=text,
        ))
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ollama_client] = make_mock_ollama
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed()
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_ollama_client, None)


def test_recap_manglish():
    response = client.post("/api/recap", json={"language": "manglish"})
    assert response.status_code == 200
    data = response.json()
    assert data["fallback"] is False
    assert "budget report" in data["recap"].lower()
    assert len(data["action_items"]) == 1
    assert len(data["evidence"]) == 2


def test_recap_person_filter():
    response = client.post("/api/recap", json={"language": "en", "person": "priya"})
    assert response.status_code == 200
    assert len(response.json()["evidence"]) == 1


def test_recap_bad_language():
    response = client.post("/api/recap", json={"language": "klingon"})
    assert response.status_code == 422
