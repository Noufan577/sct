from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.repositories.db_repository import DBRepository

router = APIRouter(prefix="/api/identities", tags=["Speaker Identity"])


def _repo(db: Session = Depends(get_db)) -> DBRepository:
    return DBRepository(db)


@router.get("")
def list_identities(meeting_id: Optional[str] = None, repo: DBRepository = Depends(_repo)):
    """All stored speaker-label → person mappings (with confidence + evidence)."""
    try:
        rows = repo.list_speaker_identities(meeting_id)
        return [
            {
                "id": r.id,
                "meetily_id": r.meetily_id,
                "speaker_label": r.speaker_label,
                "person_name": r.person_name,
                "confidence": r.confidence,
                "confirmed": bool(r.confirmed),
                "method": r.method,
                "evidence_segment_id": r.evidence_segment_id,
                "evidence_text": r.evidence_text,
            }
            for r in rows
        ]
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("/{identity_id}/confirm")
def confirm_identity(identity_id: int, body: dict, repo: DBRepository = Depends(_repo)):
    """Manually confirm a speaker → person mapping. Confirmed mappings are
    reused globally for the same speaker label in future meetings."""
    name = (body or {}).get("person_name")
    if not isinstance(name, str) or not name.strip():
        raise HTTPException(status_code=422, detail="person_name is required")
    try:
        row = repo.confirm_speaker_identity(identity_id, name.strip())
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")
    if not row:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {
        "id": row.id,
        "speaker_label": row.speaker_label,
        "person_name": row.person_name,
        "confirmed": True,
        "method": row.method,
    }
