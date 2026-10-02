"""API tests for Phase 5: POST /api/query."""

import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock
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


def make_mock_ollama(answer="Rahul's budget report went from committed to completed.", cites=None):
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({"answer": answer, "cites": cites if cites is not None else [1, 2, 3]})
    })
    return mock


client = TestClient(app)


def _seed():
    db = TestingSessionLocal()
    meetings = {}
    for mid, title in (("demo-m1", "Sprint planning"), ("demo-m2", "Mid-sprint"), ("demo-m3", "Review")):
        m = MeetingModel(meetily_id=mid, title=title)
        db.add(m)
        db.commit()
        db.refresh(m)
        meetings[mid] = m.id
    rows = [
        ("demo-m1", "COMMITTED", "Prepare the budget report", "I will prepare the budget report."),
        ("demo-m2", "OPEN", "Prepare budget report for Q3", "The budget report is still open."),
        ("demo-m3", "COMPLETED", "Prepare the budget report", "The budget report is done."),
    ]
    for mid, status, commitment, text in rows:
        db.add(CommitmentModel(
            meeting_id=meetings[mid],
            person="Rahul",
            commitment=commitment,
            status=status,
            evidence_segment_id="s1",
            evidence_speaker="Rahul",
            evidence_timestamp=1.0,
            evidence_text=text,
        ))
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_ollama_client] = lambda: make_mock_ollama()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed()
    yield
    app.dependency_overrides.pop(get_db, None)
    app.dependency_overrides.pop(get_ollama_client, None)


def test_query_rahul_action():
    response = client.post("/api/query", json={"question": "What happened to Rahul's action?"})
    assert response.status_code == 200
    data = response.json()
    assert data["fallback"] is False
    assert "Rahul" in data["answer"]
    assert len(data["evidence"]) == 3
    assert [e["status"] for e in data["evidence"]] == ["COMMITTED", "OPEN", "COMPLETED"]
    for e in data["evidence"]:
        assert e["evidence"]["text"]


def test_query_person_filter():
    response = client.post("/api/query", json={"question": "budget report", "person": "rahul"})
    assert response.status_code == 200
    assert len(response.json()["evidence"]) == 3

    response = client.post("/api/query", json={"question": "budget report", "person": "Nobody"})
    assert response.status_code == 200
    assert response.json()["evidence"] == []
    assert response.json()["fallback"] is True


def test_query_no_match():
    response = client.post("/api/query", json={"question": "Weather on Mars?"})
    assert response.status_code == 200
    data = response.json()
    assert "don't have" in data["answer"]
    assert data["evidence"] == []


def test_query_empty_question():
    response = client.post("/api/query", json={"question": "   "})
    assert response.status_code == 422
