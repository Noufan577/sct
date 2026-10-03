from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# Evidence Response
class EvidenceResponse(BaseModel):
    speaker: str
    timestamp: Optional[float]
    text: str
    model_config = {"from_attributes": True}

# Commitment Response
class CommitmentResponse(BaseModel):
    id: int
    meeting_id: int
    person: str
    commitment: str
    deadline: Optional[str]
    status: str
    created_at: datetime
    evidence: EvidenceResponse
    model_config = {"from_attributes": True}

# Meeting Response
class MeetingResponse(BaseModel):
    id: int
    meetily_id: str
    title: Optional[str]
    created_at: datetime
    model_config = {"from_attributes": True}

# Meeting Detail Response (includes commitments)
class MeetingDetailResponse(MeetingResponse):
    commitments: List[CommitmentResponse] = []
    model_config = {"from_attributes": True}

# Timeline responses (Phase 4: cross-meeting memory)
class TimelineEvidenceResponse(BaseModel):
    speaker: str
    timestamp: Optional[float]
    text: str
    segment_id: str

class TimelineItemResponse(BaseModel):
    commitment_id: int
    person: str
    commitment: str
    deadline: Optional[str]
    original_deadline: Optional[str] = None
    deadline_changed_at: Optional[str] = None
    status: str
    meeting_id: str
    meeting_title: Optional[str]
    evidence: TimelineEvidenceResponse

class TimelineThreadResponse(BaseModel):
    thread_id: str
    person: str
    topic: str
    meeting_count: int
    item_count: int
    items: List[TimelineItemResponse]

# Query responses (Phase 5: questions over history)
class QueryRequest(BaseModel):
    question: str
    person: Optional[str] = None
    top_k: int = 5

class QueryResponse(BaseModel):
    answer: str
    evidence: List[TimelineItemResponse]
    fallback: bool

# Transcription responses (Phase 7: speech-to-text)
class TranscribeResponse(BaseModel):
    transcript: str
    engine: str
    language_code: str

# Graph responses (meeting relations from LadybugDB)
class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    status: Optional[str] = None

class GraphEdge(BaseModel):
    source: str
    target: str
    label: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]

# Recap responses (Phase 8: bilingual output)
class RecapRequest(BaseModel):
    language: str = "en"
    person: Optional[str] = None

class RecapResponse(BaseModel):
    recap: str
    action_items: List[str]
    evidence: List[TimelineItemResponse]
    fallback: bool
