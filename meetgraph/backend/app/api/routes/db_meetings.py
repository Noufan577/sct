from fastapi import APIRouter, HTTPException, Depends
from typing import List
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import MeetingModel
from app.api.responses import MeetingResponse, MeetingDetailResponse, CommitmentResponse, EvidenceResponse

router = APIRouter(prefix="/api/meetings", tags=["Stored Meetings"])

def _map_commitment(c) -> CommitmentResponse:
    evidence = EvidenceResponse(
        speaker=c.evidence_speaker,
        timestamp=c.evidence_timestamp,
        text=c.evidence_text
    )
    return CommitmentResponse(
        id=c.id,
        meeting_id=c.meeting_id,
        person=c.person,
        commitment=c.commitment,
        deadline=c.deadline,
        status=c.status,
        created_at=c.created_at,
        evidence=evidence
    )

@router.get("", response_model=List[MeetingResponse])
def list_stored_meetings(db: Session = Depends(get_db)):
    meetings = db.query(MeetingModel).all()
    return meetings

@router.get("/{meeting_id}", response_model=MeetingDetailResponse)
def get_stored_meeting(meeting_id: str, db: Session = Depends(get_db)):
    meeting = db.query(MeetingModel).filter(MeetingModel.meetily_id == meeting_id).first()
    if not meeting and meeting_id.isdigit():
        meeting = db.query(MeetingModel).filter(MeetingModel.id == int(meeting_id)).first()
        
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")
        
    response = MeetingDetailResponse(
        id=meeting.id,
        meetily_id=meeting.meetily_id,
        title=meeting.title,
        created_at=meeting.created_at,
        commitments=[_map_commitment(c) for c in meeting.commitments]
    )
    return response
