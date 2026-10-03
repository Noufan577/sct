import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from app.models.ingestion.transcript import Transcript, TranscriptSegment

SELF_INTRO = re.compile(r"\b(?i:i am|i'm|this is|my name is|it'?s|hi i am|hey i am)\s+([A-Z][a-z]{2,})\b")
GREET_INTRO = re.compile(r"\b(?i:hi|hello|hey|thanks|thank you|welcome|good morning|good afternoon),?\s+([A-Z][a-z]{2,})\b")
ADDRESSED = re.compile(r"\b([A-Z][a-z]{2,})[,!]\s")
COMMON = {"Yes", "Yeah", "Sure", "Okay", "Thanks", "Thank", "Sorry", "Please", "Good", "Hello", "Hi", "Hey", "Welcome"}

def _extract_names_from_text(segments: List[Dict[str, Any]]) -> Dict[str, str]:
    """
    Scan the transcript text itself to find speaker -> real name mappings.
    E.g. 'Hi, Jessica. Thanks for joining.' -> speaker 23 -> 'Jessica'
    Or 'I am Rahul' from speaker 24 -> speaker 24 -> 'Rahul'
    Returns a mapping of speaker_label -> best_guess_name.
    """
    # Group text by speaker
    speaker_text: Dict[str, List[str]] = {}
    for seg in segments:
        label = str(seg.get("detected_meeting_speaker_id") or seg.get("assigned_meeting_speaker_id") or seg.get("speaker") or "")
        if not label:
            continue
        speaker_text.setdefault(label, []).append(seg.get("text") or "")

    # Collect all segments for cross-speaker mention lookup
    name_map: Dict[str, str] = {}

    # Pass 1: self introductions from own speech
    for label, texts in speaker_text.items():
        for text in texts:
            hits = SELF_INTRO.findall(text)
            for h in hits:
                if h not in COMMON:
                    name_map[label] = h
                    break
            if label in name_map:
                break

    # Pass 2: another speaker greets/addresses this speaker by name
    # Build an ordered list of (speaker_label, text) for context
    ordered = []
    for seg in segments:
        label = str(seg.get("detected_meeting_speaker_id") or seg.get("assigned_meeting_speaker_id") or seg.get("speaker") or "")
        if label:
            ordered.append((label, seg.get("text") or ""))

    # Collect all labels
    all_labels = list(speaker_text.keys())
    
    for label in all_labels:
        if label in name_map:
            continue
        # Look for other speakers addressing a name right before this speaker talks
        for i, (seg_label, text) in enumerate(ordered):
            if seg_label == label:
                continue  # only look at OTHER speakers
            # Check next utterance belongs to someone we can potentially link
            greet_hits = GREET_INTRO.findall(text)
            addr_hits = [h for h in ADDRESSED.findall(text) if h not in COMMON]
            candidates = [h for h in (greet_hits + addr_hits) if h not in COMMON]
            if candidates:
                # If the very next segment is from a different speaker, that speaker IS the person being addressed
                if i + 1 < len(ordered):
                    next_label, _ = ordered[i + 1]
                    if next_label != seg_label and next_label not in name_map:
                        name_map[next_label] = candidates[0]

    return name_map


def parse_meetily_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None

def normalize_transcript(meeting_id: str, meetily_segments: List[Dict[str, Any]]) -> Transcript:
    """
    Converts a raw Meetily transcript into a normalized MeetGraph Transcript.
    Also pre-scans the text to extract real names from conversational cues
    (e.g. 'Hi, Jessica') and replaces numeric speaker IDs with real names where found.
    """
    if not meetily_segments:
        return Transcript(meeting_id=meeting_id, segments=[])

    # Pre-scan ALL segments to build a name map (numeric_id -> real_name)
    name_hints = _extract_names_from_text(meetily_segments)

    normalized_segments = []
    for idx, raw_segment in enumerate(meetily_segments):
        if not isinstance(raw_segment, dict):
            continue

        text = raw_segment.get("text") or ""

        segment_id = raw_segment.get("id") or f"unknown-segment-{idx}"

        # Use detected_meeting_speaker_id (a number) as the canonical label
        numeric_id = raw_segment.get("detected_meeting_speaker_id") or raw_segment.get("assigned_meeting_speaker_id")
        speaker_label_raw = raw_segment.get("speaker") or str(numeric_id) if numeric_id is not None else None
        speaker_key = str(numeric_id) if numeric_id is not None else speaker_label_raw

        # Swap in the real name if we found one from the text
        if speaker_key and speaker_key in name_hints:
            speaker = name_hints[speaker_key]
        else:
            speaker = f"Speaker {numeric_id}" if numeric_id is not None else speaker_key

        start_time_str = raw_segment.get("start") or raw_segment.get("timestamp") or raw_segment.get("audio_start_time")
        start_time = parse_meetily_timestamp(str(start_time_str)) if start_time_str else None

        duration = raw_segment.get("duration")
        end_time = None
        if start_time and duration is not None:
            try:
                end_time = start_time + timedelta(seconds=float(duration))
            except (ValueError, TypeError):
                pass

        normalized_segments.append(TranscriptSegment(
            segment_id=str(segment_id),
            speaker=speaker,
            start_time=start_time,
            end_time=end_time,
            text=str(text)
        ))

    return Transcript(meeting_id=meeting_id, segments=normalized_segments)
