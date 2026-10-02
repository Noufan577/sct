from typing import List, Dict, Any
from app.integrations.meetily.client import MeetilyClient

class MeetilyService:
    def __init__(self, client: MeetilyClient = None):
        self.client = client or MeetilyClient()

    async def list_meetings(self) -> List[Dict[str, Any]]:
        """List all available meetings using the Meetily API."""
        return await self.client.list_meetings()

    async def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Get details for a specific meeting."""
        return await self.client.get_meeting(meeting_id)

    async def get_transcript(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get the transcript for a specific meeting."""
        return await self.client.get_transcript(meeting_id)
