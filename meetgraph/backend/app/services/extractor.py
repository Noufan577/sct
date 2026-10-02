import json
import logging
from typing import List, Optional
from pydantic import BaseModel
from app.models.ingestion.transcript import Transcript, TranscriptSegment
from app.models.domain.commitment import Commitment, Evidence
from app.integrations.ollama.client import OllamaClient

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You extract TASK ASSIGNMENTS from meeting transcripts. A commitment exists ONLY when all three hold:
1. OWNER: a specific person takes on the task (says "I will..." or is told "Arjun, do..." and accepts).
2. ACTION: a concrete, doable task (prepare a report, book tickets, send an email).
3. EVIDENCE: the task is stated in the segment — never guessed from context.

REJECT (return nothing for) all of these:
- Greetings and pleasantries: "Good morning", "How are you", "You too", "Have a productive day"
- Acknowledgements without a task: "Sure, sir", "You're welcome", "Thank you", "Sounds good"
- Sentence fragments with no task: "Have", "a productive", "day."
- Status reports with no new task: "The report is done", "I already sent it"
- Vague intentions with no concrete action: "I'll look into it", "Let's see", "We should do better"

If NO segment contains a task assignment, return {"commitments": []}.
Return ONLY valid JSON in the exact format: {"commitments": [{"segment_id": "...", "person": "...", "commitment": "<short task description>", "deadline": "..."}]}
Omit "deadline" when none is stated. The person is the one DOING the task."""

class CommitmentExtractor:
    def __init__(self, ollama_client: OllamaClient = None):
        self.client = ollama_client or OllamaClient()
        
    async def extract_from_transcript(self, transcript: Transcript) -> List[Commitment]:
        """
        Process the transcript segments in chunks and extract commitments.
        """
        all_commitments = []
        
        # Process 25 segments at a time to reduce roundtrips while keeping token count reasonable
        chunk_size = 25
        segments = transcript.segments
        
        for i in range(0, len(segments), chunk_size):
            chunk = segments[i:i + chunk_size]
            prompt = self._build_prompt(chunk)
            
            try:
                response = await self.client.generate(
                    prompt=prompt, 
                    system=SYSTEM_PROMPT,
                    format="json"
                )
                
                response_text = response.get("response", "")
                parsed = json.loads(response_text)
                
                # Safely parse the result
                extracted = parsed.get("commitments", [])
                
                for ext in extracted:
                    # Resolve evidence against the original chunk
                    segment_id = ext.get("segment_id")
                    source_segment = self._find_segment(chunk, segment_id)
                    
                    if not source_segment:
                        # If LLM hallucinates a segment_id or text, we discard or log it.
                        logger.warning(f"Extracted commitment with invalid segment_id: {segment_id}")
                        continue
                        
                    ts = source_segment.start_time.timestamp() if source_segment.start_time else None
                    
                    evidence = Evidence(
                        meeting_id=transcript.meeting_id,
                        segment_id=source_segment.segment_id,
                        speaker=source_segment.speaker or "Unknown",
                        timestamp=ts,
                        text=source_segment.text
                    )
                    
                    commitment = Commitment(
                        person=ext.get("person", source_segment.speaker or "Unknown"),
                        commitment=ext.get("commitment", ""),
                        deadline=ext.get("deadline"),
                        status="COMMITTED",
                        evidence=evidence
                    )
                    
                    all_commitments.append(commitment)
                    
            except Exception as e:
                logger.error(f"Error extracting commitments from chunk: {e}")
                continue
                
        return all_commitments
        
    def _build_prompt(self, segments: List[TranscriptSegment]) -> str:
        prompt = "Transcript segments to analyze:\n\n"
        for seg in segments:
            speaker = seg.speaker or "Unknown"
            prompt += f"[{seg.segment_id}] {speaker}: {seg.text}\n"
        return prompt

    def _find_segment(self, segments: List[TranscriptSegment], segment_id: str) -> Optional[TranscriptSegment]:
        for seg in segments:
            if seg.segment_id == segment_id:
                return seg
        return None
