from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from app.db.database import Base

class MeetingModel(Base):
    __tablename__ = "meetings"

    id = Column(Integer, primary_key=True, index=True)
    meetily_id = Column(String, unique=True, index=True, nullable=False)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    commitments = relationship("CommitmentModel", back_populates="meeting")


class CommitmentModel(Base):
    __tablename__ = "commitments"

    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), nullable=False)
    person = Column(String, nullable=False)
    commitment = Column(Text, nullable=False)
    deadline = Column(String, nullable=True)
    # --- Drift tracking ---
    original_deadline = Column(String, nullable=True)   # Deadline as first stated; never overwritten
    deadline_changed_at = Column(String, nullable=True)  # meetily_id of meeting where deadline changed
    status = Column(String, default="COMMITTED")  # PROPOSED|COMMITTED|OPEN|DONE|SLIPPED
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Evidence fields embedded for simplicity
    evidence_segment_id = Column(String, nullable=False)
    evidence_speaker = Column(String, nullable=False)
    evidence_timestamp = Column(Float, nullable=True)
    evidence_text = Column(Text, nullable=False)

    meeting = relationship("MeetingModel", back_populates="commitments")
    status_history = relationship(
        "CommitmentStatusHistory",
        back_populates="commitment",
        order_by="CommitmentStatusHistory.changed_at",
    )


class CommitmentStatusHistory(Base):
    """Immutable audit log of every status transition for a commitment."""
    __tablename__ = "commitment_status_history"

    id = Column(Integer, primary_key=True, index=True)
    commitment_id = Column(Integer, ForeignKey("commitments.id"), nullable=False)
    old_status = Column(String, nullable=True)   # None on first creation
    new_status = Column(String, nullable=False)
    changed_by = Column(String, nullable=True)   # "system" | "user" | "extractor"
    note = Column(Text, nullable=True)
    changed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    commitment = relationship("CommitmentModel", back_populates="status_history")


class SpeakerIdentityModel(Base):
    __tablename__ = "speaker_identities"

    id = Column(Integer, primary_key=True, index=True)
    meetily_id = Column(String, index=True, nullable=False)
    speaker_label = Column(String, nullable=False)
    person_name = Column(String, nullable=False)
    confidence = Column(Float, default=0.0)
    confirmed = Column(Integer, default=0)  # 0/1
    evidence_segment_id = Column(String, nullable=True)
    evidence_text = Column(Text, nullable=True)
    method = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
