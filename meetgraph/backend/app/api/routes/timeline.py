from fastapi import APIRouter, HTTPException, Depends, Query
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.repositories.db_repository import DBRepository, COMMITMENT_STATUSES
from app.services.linking import build_timeline, normalize_person
from app.api.responses import TimelineThreadResponse, TimelineItemResponse, TimelineEvidenceResponse

router = APIRouter(prefix="/api/timeline", tags=["Cross-Meeting Timeline"])


def _get_repo(db: Session = Depends(get_db)) -> DBRepository:
    return DBRepository(db)


def _item_to_response(item: Dict[str, Any]) -> TimelineItemResponse:
    ev = item.get("evidence") or {}
    return TimelineItemResponse(
        commitment_id=item.get("commitment_id"),
        commitment=item.get("commitment") or "",
        deadline=item.get("deadline"),
        original_deadline=item.get("original_deadline"),
        deadline_changed_at=item.get("deadline_changed_at"),
        status=item.get("status") or "COMMITTED",
        meeting_id=item.get("meeting_id") or "",
        meeting_title=item.get("meeting_title"),
        evidence=TimelineEvidenceResponse(
            speaker=ev.get("speaker") or "Unknown",
            timestamp=ev.get("timestamp"),
            text=ev.get("text") or "",
            segment_id=ev.get("segment_id") or "",
        ),
    )


@router.get("", response_model=List[TimelineThreadResponse])
def get_timeline(person: Optional[str] = Query(default=None), repo: DBRepository = Depends(_get_repo)):
    """Return cross-meeting commitment threads, optionally filtered by
    person (case-insensitive). Each thread links the same person's
    similar commitments across meetings in chronological order, with
    per-item evidence and drift information."""
    try:
        items = repo.get_all_commitments()
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")
    if person:
        wanted = normalize_person(person)
        items = [i for i in items if normalize_person(i.get("person")) == wanted]
    try:
        raw_threads = build_timeline(items)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to build timeline")

    # Convert raw dicts to response models
    result = []
    for thread in raw_threads:
        result.append(
            TimelineThreadResponse(
                thread_id=thread["thread_id"],
                person=thread.get("person") or "Unknown",
                topic=thread.get("topic") or "",
                meeting_count=thread.get("meeting_count", 1),
                item_count=thread.get("item_count", 1),
                items=[_item_to_response(i) for i in thread.get("items", [])],
            )
        )
    return result


@router.patch("/commitments/{commitment_id}/status")
def update_status(commitment_id: int, status: str = Query(...), repo: DBRepository = Depends(_get_repo)):
    """Update a commitment's lifecycle status.
    Valid statuses: PROPOSED, COMMITTED, OPEN, DONE, SLIPPED, COMPLETED."""
    if status not in COMMITMENT_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(COMMITMENT_STATUSES)}",
        )
    try:
        updated = repo.update_commitment_status(commitment_id, status, changed_by="user")
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")
    if not updated:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return {"id": updated.id, "status": updated.status}
