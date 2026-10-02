import asyncio
import os
import sys
import httpx

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.main import app

async def main():
    print("Testing /api/meetings endpoint via FastAPI app directly...")
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        print("Fetching /api/meetings...")
        response = await client.get("/api/meetings")
        print(f"Status: {response.status_code}")
        
        meetings = response.json()
        print(f"Found {len(meetings)} meetings.")
        
        if meetings:
            meeting_id = meetings[0].get("id")
            
            print(f"\nFetching /api/meetings/{meeting_id}...")
            m_response = await client.get(f"/api/meetings/{meeting_id}")
            print(f"Status: {m_response.status_code}")
            print(f"Meeting Title: {m_response.json().get('title')}")
            
            print(f"\nFetching /api/meetings/{meeting_id}/transcript...")
            t_response = await client.get(f"/api/meetings/{meeting_id}/transcript")
            print(f"Status: {t_response.status_code}")
            print(f"Transcript segments count: {len(t_response.json())}")

if __name__ == "__main__":
    asyncio.run(main())
