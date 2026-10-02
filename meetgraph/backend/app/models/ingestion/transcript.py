from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class TranscriptSegment(BaseModel):
    segment_id: str
    speaker: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    text: str

class Transcript(BaseModel):
    meeting_id: str
    segments: List[TranscriptSegment] = Field(default_factory=list)
