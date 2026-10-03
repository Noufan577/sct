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
    """All stored speaker-label -> person mappings (with confidence + evidence)."""
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


from pydantic import BaseModel


class ConfirmIdentityRequest(BaseModel):
    person_name: str


@router.post("/{identity_id}/confirm")
def confirm_identity(identity_id: int, req: ConfirmIdentityRequest, repo: DBRepository = Depends(_repo)):
    """Manually confirm a speaker -> person mapping. Confirmed mappings are
    reused globally for the same speaker label in future meetings, and all
    existing commitments are retroactively updated with the correct name."""
    name = req.person_name
    if not name.strip():
        raise HTTPException(status_code=422, detail="person_name is required")
    try:
        row = repo.confirm_speaker_identity(identity_id, name.strip())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    if not row:
        raise HTTPException(status_code=404, detail="Identity not found")
    return {
        "id": row.id,
        "speaker_label": row.speaker_label,
        "person_name": row.person_name,
        "confirmed": True,
        "method": row.method,
    }


@router.post("/{identity_id}/suggest")
async def suggest_name(identity_id: int, repo: DBRepository = Depends(_repo)):
    """Ask Ollama to suggest a real name for a low-confidence speaker identity
    by analyzing their full transcript text from all meetings."""
    from app.db.models import SpeakerIdentityModel, CommitmentModel  # noqa
    from app.integrations.ollama.client import OllamaClient
    import json

    db = repo.db
    row = db.query(SpeakerIdentityModel).filter(SpeakerIdentityModel.id == identity_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Identity not found")

    speaker_label = row.speaker_label

    # Gather all evidence text snippets we have for this speaker
    evidence_rows = (
        db.query(CommitmentModel)
        .filter(
            (CommitmentModel.evidence_speaker == speaker_label) |
            (CommitmentModel.person == speaker_label)
        )
        .all()
    )
    snippets = [c.evidence_text for c in evidence_rows if c.evidence_text]

    if not snippets and row.evidence_text:
        snippets = [row.evidence_text]

    if not snippets:
        return {"suggested_name": None, "reason": "No transcript evidence available for this speaker."}

    combined = "\n".join(snippets[:20])  # limit to 20 snippets

    system_prompt = (
        "You are analyzing meeting transcript excerpts spoken by or about one specific speaker. "
        "Based on the content, deduce the real first name of this person. "
        "Look for: self-introductions ('I am X', 'This is X'), being addressed by name ('Hi X', 'Thanks X,'), "
        "or contextual clues. "
        "Return ONLY a JSON object: {\"name\": \"FirstName\", \"confidence\": 0.0-1.0, \"reason\": \"...\"}. "
        "If you cannot determine the name with confidence > 0.5, return {\"name\": null, \"confidence\": 0.0, \"reason\": \"...\"}."
    )

    try:
        client = OllamaClient()
        resp = await client.generate(prompt=combined, system=system_prompt, format="json")
        result = json.loads(resp.get("response", "{}"))
        return {
            "identity_id": identity_id,
            "speaker_label": speaker_label,
            "suggested_name": result.get("name"),
            "confidence": result.get("confidence", 0.0),
            "reason": result.get("reason", ""),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM inference failed: {e}")
