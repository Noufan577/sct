import httpx
from typing import Dict, Any, List, Optional
import logging

from app.core.config import settings
from app.integrations.meetily.exceptions import (
    MeetilyClientError,
    MeetilyConnectionError,
    MeetilyAuthenticationError,
    MeetilyNotFoundError,
    MeetilyApiError
)

logger = logging.getLogger(__name__)

class MeetilyClient:
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0
    ):
        self.base_url = (base_url or settings.MEETILY_BASE_URL).rstrip('/')
        self.api_key = api_key or settings.MEETILY_API_KEY
        self.timeout = timeout
        
    def _get_client(self) -> httpx.AsyncClient:
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=self.timeout
        )

    def _handle_response(self, response: httpx.Response) -> Any:
        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            if response.status_code in (401, 403):
                raise MeetilyAuthenticationError(
                    f"Authentication failed: {response.text}"
                ) from e
            elif response.status_code == 404:
                raise MeetilyNotFoundError(
                    f"Resource not found: {response.url}"
                ) from e
            else:
                raise MeetilyApiError(
                    f"API Error ({response.status_code}): {response.text}",
                    status_code=response.status_code
                ) from e
                
        return response.json()

    async def check_availability(self) -> bool:
        """Check if the Meetily API is available and credentials are valid."""
        try:
            # We use /v1/meetings as a simple connectivity and auth check
            async with self._get_client() as client:
                response = await client.get("/v1/meetings")
                self._handle_response(response)
            return True
        except (httpx.RequestError, MeetilyClientError) as e:
            logger.warning(f"Meetily API availability check failed: {e}")
            return False

    async def list_meetings(self) -> List[Dict[str, Any]]:
        """List all available meetings."""
        try:
            async with self._get_client() as client:
                response = await client.get("/v1/meetings")
                data = self._handle_response(response)
                # The API returns {"meetings": [...], ...}
                return data.get("meetings", [])
        except httpx.RequestError as e:
            raise MeetilyConnectionError(f"Connection failed: {str(e)}") from e

    async def get_meeting(self, meeting_id: str) -> Dict[str, Any]:
        """Get details for a specific meeting."""
        try:
            async with self._get_client() as client:
                response = await client.get(f"/v1/meetings/{meeting_id}")
                return self._handle_response(response)
        except httpx.RequestError as e:
            raise MeetilyConnectionError(f"Connection failed: {str(e)}") from e

    async def get_transcript(self, meeting_id: str) -> List[Dict[str, Any]]:
        """Get the transcript for a specific meeting."""
        try:
            async with self._get_client() as client:
                response = await client.get(f"/v1/meetings/{meeting_id}/transcript")
                data = self._handle_response(response)
                # The API returns {"segments": [...], "meeting_id": "...", "title": "..."}
                return data.get("segments", [])
        except httpx.RequestError as e:
            raise MeetilyConnectionError(f"Connection failed: {str(e)}") from e
