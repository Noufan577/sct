import json
import logging
import re
from typing import List, Optional
from pydantic import BaseModel
from app.models.ingestion.transcript import Transcript, TranscriptSegment
from app.models.domain.commitment import Commitment, Evidence
from app.integrations.ollama.client import OllamaClient

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────
#  TIER 1 — STRICT SYSTEM PROMPT
#  Forces the LLM to self-classify each extraction with a "task_type"
#  so we can programmatically reject low-confidence types downstream.
# ──────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are a STRICT task-assignment extractor. You identify ONLY firm, actionable task assignments from meeting transcripts.

A VALID task assignment requires ALL of the following:
1. NAMED OWNER — The person who will PERFORM and DELIVER the work. This is ALWAYS the person receiving the task, never the person assigning it.
2. CONCRETE ACTION — A tangible deliverable or action verb (e.g. "prepare a report", "send the invoice", "schedule a meeting", "deploy the fix"). The action must produce an observable output.
3. EXPLICIT STATEMENT — The task must be clearly stated in the transcript text, not inferred.

CRITICAL RULE — WHO IS THE "person":
- "Jessica, please prepare the report" -> person = Jessica (she does the work)
- "I need you to prepare the report" -> person = the one being spoken TO (the listener), NOT the speaker saying this
- "Can you finish the analysis by Friday?" -> person = the one being asked, NOT the questioner
- The manager/boss/assigner who GIVES the task is NEVER the person. The RECIPIENT of the assignment is always the person.
- Look at which speaker is being addressed or responds with agreement. THAT is the person.
- If a manager says "I have a task for you" to someone, the SOMEONE is the person, not the manager.

ALWAYS REJECT the following — return NOTHING for them:
- Greetings: "Good morning", "How are you", "Have a great day"
- Agreements/pleasantries: "Sure", "Sounds good", "You're welcome", "Okay", "Thank you"
- Questions without assignments: "Can you confirm...?", "What do you think?"
- Opinions or clarifications: "I think the numerator is...", "External contributors shouldn't be counted"
- Status updates (past tense, already done): "I'm checking right now", "The report is done"
- Trivial in-meeting actions: "I'll bold that", "Let me share my screen", "I'll mute myself"
- Vague intentions without a deliverable: "I'll look into it", "Let's see", "We should do better"
- Echoing/rephrasing: "Let's do that instead", "do that instead" (no new deliverable)

Return ONLY valid JSON. Format:
{"commitments": [{"segment_id": "...", "person": "<name of person WHO WILL DO the task — the recipient, never the assigner>", "commitment": "<short imperative task description>", "task_type": "DELIVERABLE|MEETING|COMMUNICATION", "deadline": "..."}]}

task_type MUST be one of:
- DELIVERABLE — produces a document, report, analysis, code, or other tangible artifact
- MEETING — schedules or organises a meeting/call
- COMMUNICATION — sends an email, message, or makes a specific outreach

Omit "deadline" when none is stated.
If NO segment contains a valid task assignment, return {"commitments": []}.
When in doubt, REJECT. False negatives are far better than false positives.\
"""

# ──────────────────────────────────────────────────────────────────────
#  TIER 2 — DETERMINISTIC POST-FILTER
#  Catches false positives the LLM still lets through.
# ──────────────────────────────────────────────────────────────────────

# Minimum word count for a commitment description to be considered real
_MIN_COMMITMENT_WORDS = 4

# Patterns that indicate the commitment text is just conversational filler
_REJECT_PATTERNS: List[re.Pattern] = [
    re.compile(p, re.IGNORECASE) for p in [
        # trivial in-meeting actions
        r"^i'?ll\s+(bold|mute|unmute|share|check|look)",
        r"^(bold|mute|unmute|share)\b",
        # echoing / vague redirects
        r"^(do|let'?s do)\s+that\b",
        # status updates / already done
        r"^(i'?m|i am)\s+(checking|looking|reading|reviewing)",
        r"^(confirming|clarifying|checking)\b",
        # opinions or clarifications
        r"^(i think|i believe|i feel|in my opinion)",
        # status reports (past tense, not a new task)
        r"^(saw|noticed|found|talked|spoke|discussed|mentioned|reviewed)\b",
        r"(i did|already|have been|was done)\b",
        # speech fragments / filler
        r"^(ask|uh|um)\s+(uh|um|I)\b",
        # one-word or no-action
        r"^(okay|sure|yes|no|thanks|thank you|sounds good|got it|right|exactly)\s*$",
    ]
]

# Valid task_type values — anything else gets rejected
_VALID_TASK_TYPES = {"DELIVERABLE", "MEETING", "COMMUNICATION"}


def _passes_post_filter(commitment_text: str, task_type: Optional[str]) -> bool:
    """Return True only if the extracted commitment survives all deterministic checks."""
    # Check minimum word count
    words = commitment_text.strip().split()
    if len(words) < _MIN_COMMITMENT_WORDS:
        logger.debug(f"FILTER/short: '{commitment_text}' ({len(words)} words)")
        return False

    # Check against rejection patterns
    for pat in _REJECT_PATTERNS:
        if pat.search(commitment_text.strip()):
            logger.debug(f"FILTER/pattern: '{commitment_text}' matched {pat.pattern}")
            return False

    # Validate task_type if provided
    if task_type and task_type.upper() not in _VALID_TASK_TYPES:
        logger.debug(f"FILTER/task_type: '{commitment_text}' had invalid type '{task_type}'")
        return False

    return True


class CommitmentExtractor:
    def __init__(self, ollama_client: OllamaClient = None):
        self.client = ollama_client or OllamaClient()
        
    async def extract_from_transcript(self, transcript: Transcript) -> List[Commitment]:
        """
        Process the transcript segments in chunks and extract commitments.
        Uses a 3-tier filtering strategy:
          Tier 1: Strict LLM system prompt with self-classification
          Tier 2: Deterministic post-filter on the LLM output
          Tier 3: Evidence-grounding (segment_id must match a real segment)
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
                    commitment_text = ext.get("commitment", "").strip()
                    task_type = ext.get("task_type")

                    # ── TIER 2: Deterministic post-filter ──
                    if not _passes_post_filter(commitment_text, task_type):
                        logger.info(f"Post-filter rejected: '{commitment_text}'")
                        continue

                    # ── TIER 3: Evidence grounding ──
                    segment_id = ext.get("segment_id")
                    source_segment = self._find_segment(chunk, segment_id)
                    
                    if not source_segment:
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
                        commitment=commitment_text,
                        deadline=ext.get("deadline"),
                        status="COMMITTED",
                        evidence=evidence
                    )
                    
                    all_commitments.append(commitment)
                    logger.info(
                        f"Accepted commitment: [{task_type}] {commitment.person} → {commitment_text}"
                    )
                    
            except Exception as e:
                logger.error(f"Error extracting commitments from chunk: {e}")
                continue

        logger.info(
            f"Extraction complete: {len(all_commitments)} commitments from "
            f"{len(segments)} segments"
        )
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
