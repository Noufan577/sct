import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base
from app.db.models import MeetingModel, CommitmentModel
from app.repositories.db_repository import DBRepository
from app.models.domain.commitment import Commitment, Evidence

# Use in-memory SQLite for testing
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    yield db
    db.close()
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def repo(db_session):
    return DBRepository(db_session)

def test_database_initializes(db_session):
    assert db_session is not None

def test_save_and_get_meeting(repo):
    meeting = repo.save_meeting("meet-1", title="Test Meeting")
    assert meeting.id is not None
    assert meeting.meetily_id == "meet-1"
    assert meeting.title == "Test Meeting"

    retrieved = repo.get_meeting("meet-1")
    assert retrieved is not None
    assert retrieved.id == meeting.id
    assert retrieved.title == "Test Meeting"

def test_duplicate_meeting(repo):
    repo.save_meeting("meet-1", title="First Title")
    repo.save_meeting("meet-1", title="Second Title") # should return existing
    
    meetings = repo.db.query(MeetingModel).all()
    assert len(meetings) == 1
    assert meetings[0].title == "First Title"

def test_save_and_get_commitments(repo):
    repo.save_meeting("meet-1", "Test Meeting")
    
    evidence = Evidence(
        meeting_id="meet-1",
        segment_id="seg-1",
        speaker="Alice",
        timestamp=12.5,
        text="I will do it."
    )
    commitment = Commitment(
        person="Alice",
        commitment="Do it",
        deadline="Tomorrow",
        evidence=evidence
    )
    
    saved = repo.save_commitments("meet-1", [commitment])
    assert len(saved) == 1
    assert saved[0].person == "Alice"
    assert saved[0].evidence_text == "I will do it."
    
    retrieved = repo.get_commitments("meet-1")
    assert len(retrieved) == 1
    assert retrieved[0].deadline == "Tomorrow"

def test_duplicate_commitments(repo):
    repo.save_meeting("meet-1", "Test")
    
    evidence = Evidence(
        meeting_id="meet-1",
        segment_id="seg-1",
        speaker="Alice",
        text="I will do it."
    )
    commitment = Commitment(
        person="Alice",
        commitment="Do it",
        evidence=evidence
    )
    
    repo.save_commitments("meet-1", [commitment])
    # Duplicate, shouldn't be added again
    repo.save_commitments("meet-1", [commitment])
    
    commitments = repo.get_commitments("meet-1")
    assert len(commitments) == 1
