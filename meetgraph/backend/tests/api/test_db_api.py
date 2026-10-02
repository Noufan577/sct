import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.database import get_db, Base
from app.db.models import MeetingModel, CommitmentModel

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    # Setup
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Add seed data
    meeting = MeetingModel(meetily_id="meet-abc", title="Test Meeting")
    db.add(meeting)
    db.commit()
    db.refresh(meeting)
    
    commitment = CommitmentModel(
        meeting_id=meeting.id,
        person="Alice",
        commitment="Finish code",
        deadline="Friday",
        evidence_segment_id="s1",
        evidence_speaker="Alice",
        evidence_timestamp=10.5,
        evidence_text="I will finish code by Friday"
    )
    db.add(commitment)
    db.commit()
    db.close()
    yield
    app.dependency_overrides.pop(get_db, None)
    # Teardown handled by drop_all on next setup

def test_list_meetings():
    response = client.get("/api/meetings")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["meetily_id"] == "meet-abc"
    assert data[0]["title"] == "Test Meeting"

def test_get_meeting():
    response = client.get("/api/meetings/meet-abc")
    assert response.status_code == 200
    data = response.json()
    assert data["meetily_id"] == "meet-abc"
    assert "commitments" in data
    assert len(data["commitments"]) == 1
    assert data["commitments"][0]["person"] == "Alice"
    
def test_get_meeting_not_found():
    response = client.get("/api/meetings/fake-meet")
    assert response.status_code == 404

def test_list_commitments():
    response = client.get("/api/commitments")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["person"] == "Alice"
    assert "evidence" in data[0]
    assert data[0]["evidence"]["text"] == "I will finish code by Friday"

def test_list_commitments_filtered():
    response = client.get("/api/commitments?person=Alice")
    assert response.status_code == 200
    assert len(response.json()) == 1
    
    response = client.get("/api/commitments?person=Bob")
    assert response.status_code == 200
    assert len(response.json()) == 0

def test_get_commitment():
    # First get list to find the ID
    response = client.get("/api/commitments")
    c_id = response.json()[0]["id"]
    
    response = client.get(f"/api/commitments/{c_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["person"] == "Alice"

def test_get_commitment_not_found():
    response = client.get("/api/commitments/9999")
    assert response.status_code == 404
