from typing import List, Dict, Any
from datetime import datetime, timedelta
from app.models.ingestion.transcript import Transcript, TranscriptSegment

def parse_meetily_timestamp(ts_str: str) -> datetime | None:
    if not ts_str:
        return None
    try:
        # Handle ISO format strings
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None

def normalize_transcript(meeting_id: str, meetily_segments: List[Dict[str, Any]]) -> Transcript:
    """
    Converts a raw Meetily transcript (list of segment dictionaries) into a 
    normalized MeetGraph Transcript model.
    """
    normalized_segments = []
    
    if not meetily_segments:
        return Transcript(meeting_id=meeting_id, segments=[])
        
    for idx, raw_segment in enumerate(meetily_segments):
        if not isinstance(raw_segment, dict):
            continue
            
        text = raw_segment.get("text")
        if text is None:
            text = ""
            
        segment_id = raw_segment.get("id")
        if not segment_id:
            # Fallback ID for malformed segments missing an ID
            segment_id = f"unknown-segment-{idx}"
            
        speaker = raw_segment.get("speaker")
        if not speaker:
            # Real Meetily segments (audio1) use detected_meeting_speaker_id
            # instead of a human-friendly "speaker" label.
            speaker = raw_segment.get("detected_meeting_speaker_id") or raw_segment.get("speaker_id")

        start_time_str = raw_segment.get("start") or raw_segment.get("timestamp") or raw_segment.get("audio_start_time")
        start_time = parse_meetily_timestamp(start_time_str) if start_time_str else None
        
        duration = raw_segment.get("duration")
        end_time = None
        if start_time and duration is not None:
            try:
                end_time = start_time + timedelta(seconds=float(duration))
            except (ValueError, TypeError):
                pass
                
        normalized_segments.append(TranscriptSegment(
            segment_id=str(segment_id),
            speaker=str(speaker) if speaker else None,
            start_time=start_time,
            end_time=end_time,
            text=str(text)
        ))
        
    return Transcript(meeting_id=meeting_id, segments=normalized_segments)
