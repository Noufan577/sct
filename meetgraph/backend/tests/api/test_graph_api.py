"""API tests for GET /api/graph."""

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


def _seed():
    db = TestingSessionLocal()
    m1 = MeetingModel(meetily_id="demo-m1", title="Sprint planning")
    m2 = MeetingModel(meetily_id="demo-m2", title="Mid-sprint")
    db.add_all([m1, m2])
    db.commit()
    db.refresh(m1)
    db.refresh(m2)
    for meeting_id, person, text, status in (
        (m1.id, "Rahul", "Prepare the budget report", "COMMITTED"),
        (m2.id, "Rahul", "Prepare budget report for Q3", "OPEN"),
    ):
        db.add(CommitmentModel(
            meeting_id=meeting_id, person=person, commitment=text, status=status,
            evidence_segment_id="s1", evidence_speaker=person,
            evidence_timestamp=1.0, evidence_text=text,
        ))
    db.commit()
    db.close()


@pytest.fixture(autouse=True)
def setup_teardown():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _seed()
    yield
    app.dependency_overrides.pop(get_db, None)


def test_graph_all():
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    types = [n["type"] for n in data["nodes"]]
    assert types.count("person") == 1
    assert types.count("meeting") == 2
    assert types.count("commitment") == 2
    assert {"source": "c:1", "target": "c:2", "label": "same thread"} in [
        {"source": e["source"], "target": e["target"], "label": e["label"]} for e in data["edges"]
    ]


def test_graph_person_filter():
    response = client.get("/api/graph", params={"person": "rahul"})
    assert response.status_code == 200
    assert len(response.json()["nodes"]) == 5

    response = client.get("/api/graph", params={"person": "Nobody"})
    assert response.status_code == 200
    assert response.json() == {"nodes": [], "edges": []}
