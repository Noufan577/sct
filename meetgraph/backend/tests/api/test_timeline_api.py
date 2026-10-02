"""API tests for Phase 4: cross-meeting timeline + status updates.

Seeds the hackathon demo scenario: Rahul commits in meeting 1, the
action is still open in meeting 2, completed in meeting 3.
"""

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


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


client = TestClient(app)


def _seed_rahul_scenario():
    db = TestingSessionLocal()
    m1 = MeetingModel(meetily_id="demo-m1", title="Sprint planning")
    m2 = MeetingModel(meetily_id="demo-m2", title="Mid-sprint check")
    m3 = MeetingModel(meetily_id="demo-m3", title="Sprint review")
    db.add_all([m1, m2, m3])
    db.commit()
    for m in (m1, m2, m3):
        db.refresh(m)
    rows = [
        (m1.id, "COMMITTED", "Prepare the budget report", "I will prepare the budget report."),
        (m2.id, "OPEN", "Prepare budget report for Q3", "The budget report is still open."),
        (m3.id, "COMPLETED", "Prepare the budget report", "The budget report is done."),
        (m1.id, "COMMITTED", "Book flight tickets", "I will book flight tickets."),
    ]
    ids = []
    for meeting_id, status, commitment, text in rows:
        c = CommitmentModel(
            meeting_id=meeting_id,
            person="Rahul" if "budget" in commitment.lower() or "flight" in commitment.lower() else "X",
            commitment=commitment,
            status=status,
            evidence_segment_id="s1",
            evidence_speaker="Rahul",
            evidence_timestamp=1.0,
            evidence_text=text,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        ids.append(c.id)
    db.close()
    return ids


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    app.dependency_overrides.pop(get_db, None)


def test_timeline_groups_rahul_action():
    _seed_rahul_scenario()
    response = client.get("/api/timeline")
    assert response.status_code == 200
    threads = response.json()
    # Rahul budget thread + Rahul flight thread
    assert len(threads) == 2
    budget = next(t for t in threads if "budget" in t["topic"].lower())
    assert budget["person"] == "Rahul"
    assert budget["meeting_count"] == 3
    assert [i["status"] for i in budget["items"]] == ["COMMITTED", "OPEN", "COMPLETED"]
    assert [i["meeting_id"] for i in budget["items"]] == ["demo-m1", "demo-m2", "demo-m3"]
    # Evidence on every item
    for item in budget["items"]:
        assert item["evidence"]["text"]
        assert item["evidence"]["speaker"] == "Rahul"


def test_timeline_person_filter_case_insensitive():
    _seed_rahul_scenario()
    response = client.get("/api/timeline", params={"person": "rahul"})
    assert response.status_code == 200
    assert len(response.json()) == 2

    response = client.get("/api/timeline", params={"person": "Nobody"})
    assert response.status_code == 200
    assert response.json() == []


def test_update_status_success():
    ids = _seed_rahul_scenario()
    response = client.patch(f"/api/timeline/commitments/{ids[0]}/status", params={"status": "COMPLETED"})
    assert response.status_code == 200
    assert response.json()["status"] == "COMPLETED"


def test_update_status_invalid():
    ids = _seed_rahul_scenario()
    response = client.patch(f"/api/timeline/commitments/{ids[0]}/status", params={"status": "DONE"})
    assert response.status_code == 422


def test_update_status_not_found():
    response = client.patch("/api/timeline/commitments/9999/status", params={"status": "OPEN"})
    assert response.status_code == 404
