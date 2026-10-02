from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import CommitmentModel
from app.api.responses import CommitmentResponse, EvidenceResponse

router = APIRouter(prefix="/api/commitments", tags=["Stored Commitments"])

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

@router.get("", response_model=List[CommitmentResponse])
def list_stored_commitments(person: Optional[str] = None, db: Session = Depends(get_db)):
    try:
        query = db.query(CommitmentModel)
        if person:
            query = query.filter(CommitmentModel.person.ilike(f"%{person}%"))
        commitments = query.all()
        return [_map_commitment(c) for c in commitments]
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error occurred")

@router.get("/{commitment_id}", response_model=CommitmentResponse)
def get_stored_commitment(commitment_id: int, db: Session = Depends(get_db)):
    try:
        commitment = db.query(CommitmentModel).filter(CommitmentModel.id == commitment_id).first()
        if not commitment:
            raise HTTPException(status_code=404, detail="Commitment not found")
        return _map_commitment(commitment)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Database error occurred")
