from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any
from app.integrations.meetily.service import MeetilyService
from app.integrations.meetily.exceptions import (
    MeetilyNotFoundError,
    MeetilyAuthenticationError,
    MeetilyConnectionError,
    MeetilyClientError
)

router = APIRouter(prefix="/api/meetily/meetings", tags=["Meetily Proxy"])

def get_meetily_service() -> MeetilyService:
    return MeetilyService()

@router.get("", response_model=List[Dict[str, Any]])
async def list_meetings(service: MeetilyService = Depends(get_meetily_service)):
    try:
        return await service.list_meetings()
    except MeetilyAuthenticationError:
        raise HTTPException(status_code=401, detail="Meetily integration authentication failed")
    except MeetilyConnectionError:
        raise HTTPException(status_code=502, detail="Failed to connect to Meetily API")
    except MeetilyClientError:
        raise HTTPException(status_code=500, detail="Meetily API error occurred")

@router.get("/{meeting_id}", response_model=Dict[str, Any])
async def get_meeting(meeting_id: str, service: MeetilyService = Depends(get_meetily_service)):
    try:
        return await service.get_meeting(meeting_id)
    except MeetilyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MeetilyAuthenticationError:
        raise HTTPException(status_code=401, detail="Meetily integration authentication failed")
    except MeetilyConnectionError:
        raise HTTPException(status_code=502, detail="Failed to connect to Meetily API")
    except MeetilyClientError:
        raise HTTPException(status_code=500, detail="Meetily API error occurred")

@router.get("/{meeting_id}/transcript", response_model=List[Dict[str, Any]])
async def get_transcript(meeting_id: str, service: MeetilyService = Depends(get_meetily_service)):
    try:
        return await service.get_transcript(meeting_id)
    except MeetilyNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except MeetilyAuthenticationError:
        raise HTTPException(status_code=401, detail="Meetily integration authentication failed")
    except MeetilyConnectionError:
        raise HTTPException(status_code=502, detail="Failed to connect to Meetily API")
    except MeetilyClientError:
        raise HTTPException(status_code=500, detail="Meetily API error occurred")
