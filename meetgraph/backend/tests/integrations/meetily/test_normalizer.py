import json
import os
import pytest
from datetime import datetime, timezone
from app.integrations.meetily.normalizer import normalize_transcript
from app.models.ingestion.transcript import Transcript, TranscriptSegment

FIXTURE_PATH = os.path.join(
    os.path.dirname(__file__), 
    "../../fixtures/meetily/transcript_sample.json"
)

@pytest.fixture
def sample_transcript_data():
    with open(FIXTURE_PATH, 'r') as f:
        return json.load(f)

def test_normalize_real_fixture(sample_transcript_data):
    # Verify that the 245-segment real transcript fixture was successfully normalized.
    normalized = normalize_transcript("meeting-123", sample_transcript_data)
    
    assert isinstance(normalized, Transcript)
    assert normalized.meeting_id == "meeting-123"
    assert len(normalized.segments) == 245
    
    first_segment = normalized.segments[0]
    assert first_segment.speaker == "Speaker"
    assert first_segment.text == "[REDACTED]"
    assert first_segment.segment_id == "transcript-abeb08f6-2670-4c06-b6be-d101f3c255ac#c0000"
    assert first_segment.start_time is not None
    assert first_segment.end_time is not None
    assert first_segment.start_time.year == 2026

def test_normalize_empty_transcript():
    normalized = normalize_transcript("meeting-123", [])
    assert len(normalized.segments) == 0
    assert normalized.meeting_id == "meeting-123"

def test_normalize_missing_optional_fields():
    # Transcript segment without optional fields
    raw_data = [
        {
            "id": "segment-1",
            "text": "Hello world"
            # Missing speaker, start, duration
        }
    ]
    normalized = normalize_transcript("meeting-123", raw_data)
    assert len(normalized.segments) == 1
    
    seg = normalized.segments[0]
    assert seg.segment_id == "segment-1"
    assert seg.text == "Hello world"
    assert seg.speaker is None
    assert seg.start_time is None
    assert seg.end_time is None

def test_normalize_empty_text():
    raw_data = [
        {
            "id": "segment-2",
            "speaker": "Alice",
            "start": "2026-10-02T09:59:45.000000+00:00"
            # Missing text
        }
    ]
    normalized = normalize_transcript("meeting-123", raw_data)
    seg = normalized.segments[0]
    assert seg.text == ""

def test_normalize_malformed_segment():
    raw_data = [
        "not-a-dict", # should be skipped
        {
            # Missing id entirely
            "text": "Valid text"
        }
    ]
    normalized = normalize_transcript("meeting-123", raw_data)
    assert len(normalized.segments) == 1
    seg = normalized.segments[0]
    assert seg.segment_id == "unknown-segment-1"
    assert seg.text == "Valid text"
