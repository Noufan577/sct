import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.db.database import init_db, SessionLocal
from app.db.models import MeetingModel, CommitmentModel
from app.integrations.meetily.service import MeetilyService
from app.services.extractor import CommitmentExtractor
from app.services.orchestrator import process_meeting

async def main():
    print("Initializing Database...")
    init_db()
    
    print("Testing Complete MeetGraph Pipeline...")
    
    db = SessionLocal()
    meetily_service = MeetilyService()
    extractor = CommitmentExtractor()
    
    # Check if we can get a meeting from Meetily
    meetings = await meetily_service.list_meetings()
    if not meetings:
        print("No meetings found in Meetily. Cannot run pipeline.")
        return
        
    meeting_id = meetings[0].get("id")
    print(f"Selected meeting: {meeting_id}")
    
    print("Running process_meeting()...")
    result = await process_meeting(meeting_id, db, meetily_service, extractor)
    
    print("\n--- Pipeline Result ---")
    print(result)
    
    print("\n--- Validating Database ---")
    saved_meeting = db.query(MeetingModel).filter(MeetingModel.meetily_id == meeting_id).first()
    print(f"Meeting in DB: {saved_meeting.title if saved_meeting else 'Not found'}")
    
    commitments = db.query(CommitmentModel).filter(CommitmentModel.meeting_id == saved_meeting.id).all() if saved_meeting else []
    print(f"Commitments in DB: {len(commitments)}")
    
    for c in commitments:
        print(f"- {c.person}: {c.commitment} (Deadline: {c.deadline})")
        print(f"  Evidence: {c.evidence_text}")
        
    db.close()

if __name__ == "__main__":
    asyncio.run(main())
