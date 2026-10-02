import asyncio
import os
import sys

# Add backend directory to path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.integrations.meetily.client import MeetilyClient

async def main():
    client = MeetilyClient()
    
    print("Checking Meetily availability...")
    is_available = await client.check_availability()
    print(f"Available: {is_available}")
    
    if not is_available:
        print("Cannot run real test, API is not available.")
        return
        
    print("\nListing meetings...")
    meetings = await client.list_meetings()
    print(f"Found {len(meetings)} meetings.")
    
    if meetings:
        meeting_id = meetings[0].get('id')
        print(f"\nFetching details for meeting {meeting_id}...")
        meeting = await client.get_meeting(meeting_id)
        print(f"Meeting title: {meeting.get('title')}")
        
        print(f"\nFetching transcript for meeting {meeting_id}...")
        transcript = await client.get_transcript(meeting_id)
        print(f"Transcript fetched! Total segments: {len(transcript)}")
        
if __name__ == "__main__":
    asyncio.run(main())
