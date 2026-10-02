from sqlalchemy.orm import Session
from app.integrations.meetily.service import MeetilyService
from app.integrations.meetily.normalizer import normalize_transcript
from app.services.extractor import CommitmentExtractor
from app.services.speaker_resolver import resolve_speakers
from app.repositories.db_repository import DBRepository

async def process_meeting(
    meeting_id: str, 
    db: Session, 
    meetily_service: MeetilyService, 
    extractor: CommitmentExtractor
):
    """
    Process a meeting:
    1. Fetch metadata and transcript from Meetily.
    2. Normalize transcript.
    3. Extract commitments via Ollama.
    4. Save to Database.
    """
    repo = DBRepository(db)

    # 1. Fetch meeting info and transcript
    meeting_data = await meetily_service.get_meeting(meeting_id)
    raw_transcript = await meetily_service.get_transcript(meeting_id)

    # 2. Normalize transcript
    normalized = normalize_transcript(meeting_id, raw_transcript)

    # 2b. Resolve speaker labels to persistent people BEFORE extraction,
    #     so commitment owners/evidence carry real names.
    from app.integrations.ollama.client import OllamaClient
    prior = repo.get_confirmed_identity_map()
    resolved = await resolve_speakers(
        [{"id": s.segment_id, "speaker": s.speaker, "text": s.text} for s in normalized.segments],
        prior_confirmed=prior,
        ollama_client=OllamaClient()
    )
    repo.save_speaker_identities(meeting_id, resolved)
    for s in normalized.segments:
        info = resolved.get(s.speaker)
        if info and info["person"] != s.speaker:
            s.speaker = info["person"]

    # 3. Extract commitments
    commitments = await extractor.extract_from_transcript(normalized)
    
    # 4. Save to DB
    title = meeting_data.get("title", f"Meeting {meeting_id}")
    repo.save_meeting(meeting_id, title=title)
    
    if commitments:
        repo.save_commitments(meeting_id, commitments)
        
        # 5. Retroactively update speaker identities if LLM inferred names
        inferred_map = {}
        for c in commitments:
            if c.person and c.evidence and c.evidence.speaker and c.person != c.evidence.speaker:
                # E.g. c.person = "Eric", c.evidence.speaker = "24"
                inferred_map[c.evidence.speaker] = {
                    "person": c.person,
                    "confidence": 0.85,
                    "evidence_segment_id": c.evidence.segment_id,
                    "evidence_text": c.evidence.text,
                    "method": "llm_inferred"
                }
        if inferred_map:
            repo.save_speaker_identities(meeting_id, inferred_map)
        
    return {
        "meeting_id": meeting_id,
        "title": title,
        "commitments_found": len(commitments)
    }
