"""Commitment intelligence endpoints:
- GET /api/drift           — commitments with changed deadlines
- GET /api/since/{mid}     — what changed since a given meeting
- GET /api/brief/{mid}     — pre-meeting brief (open commitments + drift)
- GET /api/commitments/{id}/history  — full status audit trail
- PATCH /api/commitments/{id}/status — update status (moved from timeline for clarity)
"""
from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.repositories.db_repository import DBRepository, COMMITMENT_STATUSES

router = APIRouter(prefix="/api/intel", tags=["Commitment Intelligence"])


def _repo(db: Session = Depends(get_db)) -> DBRepository:
    return DBRepository(db)


@router.get("/drift")
def get_drift(repo: DBRepository = Depends(_repo)) -> List[Dict[str, Any]]:
    """Return commitments whose deadline has slipped from the original.
    Includes original_deadline, current_deadline, person and status."""
    try:
        return repo.get_drift_report()
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build drift report")


@router.get("/since/{meeting_id}")
def get_changes_since(meeting_id: str, repo: DBRepository = Depends(_repo)) -> Dict[str, Any]:
    """Return all commitment changes (new, status changes, slipped deadlines)
    that occurred after the given meeting. Useful for 'what changed?' queries."""
    try:
        return repo.get_changes_since(meeting_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build change report")


@router.get("/brief/{meeting_id}")
def get_brief(meeting_id: str, repo: DBRepository = Depends(_repo)) -> Dict[str, Any]:
    """Pre-meeting brief: open/slipped commitments plus recent changes,
    scoped to participants/context of the upcoming meeting."""
    try:
        all_commits = repo.get_all_commitments()
        open_items = [
            c for c in all_commits
            if c["status"] in ("COMMITTED", "OPEN", "SLIPPED", "PROPOSED")
        ]
        drift = repo.get_drift_report()
        # Get changes since the most recent meeting before this one
        # (for simplicity, return last-meeting context)
        meetings_before = [
            c["meeting_id"] for c in all_commits
            if c["meeting_id"] != meeting_id
        ]
        last_meeting = meetings_before[-1] if meetings_before else None
        since = repo.get_changes_since(last_meeting) if last_meeting else {}
        return {
            "brief_for_meeting": meeting_id,
            "open_commitments": open_items,
            "slipped_deadlines": drift,
            "changes_since_last_meeting": since,
            "open_count": len(open_items),
            "slipped_count": len(drift),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build brief: {e}")


@router.get("/commitments/{commitment_id}/history")
def get_commitment_history(commitment_id: int, repo: DBRepository = Depends(_repo)) -> List[Dict[str, Any]]:
    """Return the full status audit trail for a commitment."""
    try:
        history = repo.get_status_history(commitment_id)
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    if not history:
        raise HTTPException(status_code=404, detail="Commitment not found or no history")
    return history


@router.patch("/commitments/{commitment_id}/status")
def update_status(
    commitment_id: int,
    body: dict,
    repo: DBRepository = Depends(_repo),
) -> Dict[str, Any]:
    """Update a commitment's lifecycle status.
    Body: {\"status\": \"DONE\", \"note\": \"optional reason\"}
    """
    status = (body or {}).get("status", "")
    if status not in COMMITMENT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(COMMITMENT_STATUSES)}",
        )
    note = (body or {}).get("note")
    try:
        updated = repo.update_commitment_status(commitment_id, status, changed_by="user", note=note)
    except Exception:
        raise HTTPException(status_code=500, detail="Database error")
    if not updated:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return {
        "id": updated.id,
        "status": updated.status,
        "person": updated.person,
        "commitment": updated.commitment,
    }


@router.get("/commitments/{commitment_id}/draft-reminder")
async def draft_reminder(
    commitment_id: int,
    repo: DBRepository = Depends(_repo)
) -> Dict[str, str]:
    """Draft a polite follow-up email for a commitment using Ollama."""
    from app.integrations.ollama.client import OllamaClient
    
    commits = repo.get_all_commitments()
    commitment = next((c for c in commits if c["commitment_id"] == commitment_id), None)
    if not commitment:
        raise HTTPException(status_code=404, detail="Commitment not found")
        
    client = OllamaClient()
    meeting_title = commitment.get("meeting_title") or "our previous meeting"
    prompt = (
        f"Write a short, polite, one-paragraph email to {commitment['person']} "
        f"checking in on this task they committed to: '{commitment['commitment']}'. "
        f"The task was assigned during the meeting '{meeting_title}'. "
        "Do not include a subject line, just the email body starting with a greeting. "
        "Keep it friendly and concise."
    )
    
    try:
        response = await client.generate(
            prompt=prompt, 
            system="You are a helpful executive assistant writing polite follow-up emails."
        )
        draft = response.get("response", "").strip()
        return {"draft": draft}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate draft: {str(e)}")
