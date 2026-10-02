from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.integrations.meetily.service import MeetilyService
from app.integrations.meetily.exceptions import (
    MeetilyAuthenticationError,
    MeetilyClientError,
    MeetilyConnectionError,
    MeetilyNotFoundError,
)
from app.integrations.ollama.client import OllamaClient
from app.services.extractor import CommitmentExtractor
from app.services.orchestrator import process_meeting
from app.repositories.db_repository import DBRepository
from app.api.routes.meetings import get_meetily_service
from app.api.routes.query import get_ollama_client

router = APIRouter(prefix="/api/sync", tags=["Meetily Sync"])


def get_extractor(ollama: OllamaClient = Depends(get_ollama_client)) -> CommitmentExtractor:
    return CommitmentExtractor(ollama_client=ollama)


@router.get("/status")
async def sync_status(
    db: Session = Depends(get_db),
    service: MeetilyService = Depends(get_meetily_service),
):
    """List Meetily meetings flagged with whether each is already in MeetGraph."""
    try:
        meetings = await service.list_meetings()
    except MeetilyAuthenticationError:
        raise HTTPException(status_code=401, detail="Meetily authentication failed")
    except MeetilyConnectionError:
        raise HTTPException(status_code=502, detail="Failed to connect to Meetily API")
    except MeetilyClientError:
        raise HTTPException(status_code=500, detail="Meetily API error occurred")
    try:
        repo = DBRepository(db)
        out = []
        for m in meetings:
            mid = m.get("id")
            out.append(
                {
                    "id": mid,
                    "title": m.get("title"),
                    "fetched": repo.get_meeting(mid) is not None,
                }
            )
        return out
    except Exception:
        raise HTTPException(status_code=500, detail="Database error occurred")


@router.post("/meetings/{meeting_id}")
async def import_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    service: MeetilyService = Depends(get_meetily_service),
    extractor: CommitmentExtractor = Depends(get_extractor),
):
    """Fetch one Meetily meeting into MeetGraph: transcript, normalize,
    extract commitments, store. Already-imported meetings import again
    harmlessly (meetings and commitments dedupe)."""
    try:
        return await process_meeting(meeting_id, db, service, extractor)
    except MeetilyNotFoundError:
        raise HTTPException(status_code=404, detail="Meeting not found in Meetily")
    except MeetilyAuthenticationError:
        raise HTTPException(status_code=401, detail="Meetily authentication failed")
    except MeetilyConnectionError:
        raise HTTPException(status_code=502, detail="Failed to connect to Meetily API")
    except MeetilyClientError:
        raise HTTPException(status_code=500, detail="Meetily API error occurred")
