from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.integrations.ollama.client import OllamaClient
from app.repositories.db_repository import DBRepository
from app.services.linking import normalize_person
from app.services.qa import QAService
from app.api.responses import QueryRequest, QueryResponse, TimelineItemResponse, TimelineEvidenceResponse

router = APIRouter(prefix="/api/query", tags=["Questions"])


def get_ollama_client() -> OllamaClient:
    return OllamaClient()


def _to_evidence(item: dict) -> TimelineItemResponse:
    ev = item.get("evidence") or {}
    return TimelineItemResponse(
        commitment_id=item.get("commitment_id"),
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


@router.post("", response_model=QueryResponse)
async def ask_question(
    body: QueryRequest,
    db: Session = Depends(get_db),
    ollama: OllamaClient = Depends(get_ollama_client),
):
    """Ask a natural-language question about meeting history.

    Retrieval is deterministic Python (token overlap); Ollama only
    turns the retrieved evidence into prose. Every answer ships with
    its evidence items. Falls back to an extractive answer when the
    LLM is unavailable."""
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=422, detail="Question must not be empty.")
    try:
        items = DBRepository(db).get_all_commitments()
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")
    if body.person:
        wanted = normalize_person(body.person)
        items = [i for i in items if normalize_person(i.get("person")) == wanted]
    try:
        result = await QAService(ollama_client=ollama).answer(question, items, top_k=body.top_k)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to answer question")
    return QueryResponse(
        answer=result["answer"],
        evidence=[_to_evidence(i) for i in result["cites"]],
        fallback=result["fallback"],
    )
