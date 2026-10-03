from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.integrations.ollama.client import OllamaClient
from app.repositories.db_repository import DBRepository
from app.services.linking import normalize_person
from app.services.recap import RecapService, RECAP_LANGUAGES
from app.api.responses import (
    RecapRequest,
    RecapResponse,
    TimelineEvidenceResponse,
    TimelineItemResponse,
)
from app.api.routes.query import get_ollama_client

router = APIRouter(prefix="/api/recap", tags=["Recap"])


def _to_evidence(item: dict) -> TimelineItemResponse:
    ev = item.get("evidence") or {}
    return TimelineItemResponse(
        commitment_id=item.get("commitment_id"),
        person=item.get("person") or "Unknown",
        commitment=item.get("commitment"),
        deadline=item.get("deadline"),
        status=item.get("status"),
        meeting_id=item.get("meeting_id"),
        meeting_title=item.get("meeting_title"),
        evidence=TimelineEvidenceResponse(
            speaker=ev.get("speaker") or "Unknown",
            timestamp=ev.get("timestamp"),
            text=ev.get("text") or "",
            segment_id=ev.get("segment_id") or "",
        ),
    )


@router.post("", response_model=RecapResponse)
async def make_recap(
    body: RecapRequest,
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
):
    """Generate a recap + action list in the requested language
    (en, ml, manglish), grounded on stored commitments."""
    if body.language not in RECAP_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported language. Must be one of: {', '.join(RECAP_LANGUAGES)}",
        )
    try:
        items = DBRepository(db).get_all_commitments()
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")
    if body.person:
        wanted = normalize_person(body.person)
        items = [i for i in items if normalize_person(i.get("person")) == wanted]
    try:
        result = await RecapService(ollama_client=ollama).recap(items, language=body.language)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to generate recap")
    return RecapResponse(
        recap=result["recap"],
        action_items=result["action_items"],
        evidence=[_to_evidence(i) for i in result["cites"]],
        fallback=result["fallback"],
    )
