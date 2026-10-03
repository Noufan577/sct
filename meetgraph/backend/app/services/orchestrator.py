from sqlalchemy.orm import Session
from app.integrations.meetily.service import MeetilyService
from app.integrations.meetily.normalizer import normalize_transcript, _extract_names_from_text
from app.services.extractor import CommitmentExtractor
from app.services.speaker_resolver import resolve_speakers
from app.repositories.db_repository import DBRepository
from app.services.completion_detector import detect_completions, apply_completions
import logging

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """Lowercase stripped name for fuzzy cross-meeting matching."""
    return name.strip().lower()


async def process_meeting(
    meeting_id: str,
    db: Session,
    meetily_service: MeetilyService,
    extractor: CommitmentExtractor
):
    """
    Process a meeting end-to-end:
    1. Fetch metadata and transcript from Meetily.
    2. Normalize transcript — Meetily sends numeric IDs only (no names via API).
    3. Extract real names from transcript text (e.g. 'Hi, Jessica' -> Jessica).
    4. Fall back to LLM behavioral inference for unresolved speakers.
    5. If still unresolved, keep as 'Speaker {N}'.
    6. Cross-meeting merge: if the resolved name matches a previously confirmed person,
       reuse the same canonical name so only ONE node exists per person across all meetings.
    7. Extract commitments.
    8. Save everything to DB.
    """
    repo = DBRepository(db)

    # Step 1: Fetch meeting info and raw transcript
    meeting_data = await meetily_service.get_meeting(meeting_id)
    raw_transcript = await meetily_service.get_transcript(meeting_id)

    # Step 2: Normalize -- maps numeric speaker IDs + extracts names from text greetings
    # normalizer already does Pass1 (self-intro) + Pass2 (greeted-by-name) scanning
    normalized = normalize_transcript(meeting_id, raw_transcript)

    # Step 3: Build the merged prior map for the resolver
    from app.integrations.ollama.client import OllamaClient

    # 3a. Text-extracted hints from THIS meeting's raw segments (numeric_id -> name)
    text_hints = _extract_names_from_text(raw_transcript)
    logger.info(f"Text name hints for {meeting_id}: {text_hints}")

    # 3b. Globally confirmed mappings from ALL past meetings (speaker_label -> name)
    prior_confirmed = repo.get_confirmed_identity_map()

    # 3c. Also get all confirmed person names for cross-meeting merging
    confirmed_names = repo.get_confirmed_person_names()
    # Build a lowercase lookup for fuzzy matching
    confirmed_names_lower = {_normalize_name(n): n for n in confirmed_names}

    # 3d. Merge: text hints seeded first, confirmed DB values override
    merged_prior = {}
    for k, v in text_hints.items():
        merged_prior[k] = v                  # "20" -> "Jessica"
        merged_prior[f"Speaker {k}"] = v     # "Speaker 20" -> "Jessica"
    merged_prior.update(prior_confirmed)     # confirmed DB always wins

    # Step 4: Run the speaker resolver (regex self-intro -> LLM -> fallback to label)
    resolved = await resolve_speakers(
        [{"id": s.segment_id, "speaker": s.speaker, "text": s.text} for s in normalized.segments],
        prior_confirmed=merged_prior,
        ollama_client=OllamaClient()
    )

    # Step 5: Cross-meeting person node merge
    # If the resolved name for a speaker matches a previously confirmed person name,
    # replace it with the canonical confirmed name (handles "jessica" == "Jessica").
    for label, info in resolved.items():
        resolved_name = info.get("person", "")
        normalized_resolved = _normalize_name(resolved_name)
        if normalized_resolved in confirmed_names_lower:
            canonical = confirmed_names_lower[normalized_resolved]
            if canonical != resolved_name:
                logger.info(f"Cross-meeting merge: {label} '{resolved_name}' -> '{canonical}'")
                info["person"] = canonical
                info["method"] = info.get("method", "") + "+cross_meeting_merge"

    # Persist speaker identity records
    repo.save_speaker_identities(meeting_id, resolved)

    # Apply resolved names back onto the normalized segments
    for s in normalized.segments:
        info = resolved.get(s.speaker)
        if info and info["person"] != s.speaker:
            s.speaker = info["person"]

    # Step 6: Extract commitments
    commitments = await extractor.extract_from_transcript(normalized)

    # Step 7: Save to DB
    title = meeting_data.get("title", f"Meeting {meeting_id}")
    repo.save_meeting(meeting_id, title=title)

    if commitments:
        repo.save_commitments(meeting_id, commitments)

        # Step 8: Retroactively update speaker identities if extractor inferred names
        # (e.g. LLM said "20 -> Jessica" from context even if resolver didn't)
        inferred_map = {}
        for c in commitments:
            if c.person and c.evidence and c.evidence.speaker and c.person != c.evidence.speaker:
                # Check if this inferred name merges with an existing confirmed person
                canonical_name = confirmed_names_lower.get(_normalize_name(c.person), c.person)
                inferred_map[c.evidence.speaker] = {
                    "person": canonical_name,
                    "confidence": 0.85,
                    "evidence_segment_id": c.evidence.segment_id,
                    "evidence_text": c.evidence.text,
                    "method": "llm_inferred"
                }
        if inferred_map:
            repo.save_speaker_identities(meeting_id, inferred_map)

    # Step 9: Completion Detection
    # Scan this meeting's segments for signals that PREVIOUS open commitments
    # are now completed (e.g. 'the report is done', 'I finished the analysis').
    # Build a speaker label -> resolved name map for the detector.
    resolved_name_map = {label: info["person"] for label, info in resolved.items()}
    # Also map normalized segment speakers (already rewritten above)
    for s in normalized.segments:
        resolved_name_map[s.speaker] = s.speaker

    open_commitments = repo.get_open_commitments(exclude_meeting_id=meeting_id)
    if open_commitments:
        seg_dicts = [{"id": s.segment_id, "speaker": s.speaker, "text": s.text}
                     for s in normalized.segments]
        matches = detect_completions(seg_dicts, open_commitments, resolved_name_map)
        auto_completed = apply_completions(db, matches, meeting_id)
        if auto_completed:
            logger.info(f"{auto_completed} commitment(s) auto-marked COMPLETED from {meeting_id}")
    else:
        auto_completed = 0

    return {
        "meeting_id": meeting_id,
        "title": title,
        "commitments_found": len(commitments),
        "auto_completed": auto_completed,
    }
