from pydantic import BaseModel
from typing import Optional

class Evidence(BaseModel):
    meeting_id: str
    segment_id: str
    speaker: str
    timestamp: Optional[float] = None  # Using float for duration/seconds if we parse it, or keeping it flexible
    text: str

class Commitment(BaseModel):
    person: str
    commitment: str
    deadline: Optional[str] = None
    status: str = "COMMITTED"
    evidence: Evidence
