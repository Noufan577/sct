import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from app.db.database import SessionLocal
from app.db.models import MeetingModel, CommitmentModel, CommitmentStatusHistory, SpeakerIdentityModel

db = SessionLocal()

meetily_ids = [
    "meeting-c9c2f66f-a822-441d-81dc-6cee98024460",
    "meeting-6b518b96-d8f1-451e-8801-d721bd055d5b",
    "meeting-6e1fe11c-2e6c-4547-9259-40190572f6f3"
]

for mid in meetily_ids:
    print(f"Deleting data for {mid}...")
    
    m = db.query(MeetingModel).filter(MeetingModel.meetily_id == mid).first()
    
    if m:
        commitments = db.query(CommitmentModel).filter(CommitmentModel.meeting_id == m.id).all()
        for c in commitments:
            db.query(CommitmentStatusHistory).filter(CommitmentStatusHistory.commitment_id == c.id).delete()
        
        db.query(CommitmentModel).filter(CommitmentModel.meeting_id == m.id).delete()
        db.delete(m)
        print(f"  -> Deleted meeting {mid} and its commitments.")
    else:
        print(f"  -> Meeting {mid} not found in DB.")
        
    identities_deleted = db.query(SpeakerIdentityModel).filter(SpeakerIdentityModel.meetily_id == mid).delete()
    print(f"  -> Deleted {identities_deleted} speaker identities for {mid}.")

db.commit()
db.close()
print("Database cleanup complete.")
