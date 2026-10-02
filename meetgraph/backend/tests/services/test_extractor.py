import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from app.services.extractor import CommitmentExtractor
from app.models.ingestion.transcript import Transcript, TranscriptSegment
from app.integrations.ollama.exceptions import OllamaConnectionError

@pytest.fixture
def mock_ollama():
    client = MagicMock()
    # By default, mock returns empty commitments
    client.generate = AsyncMock(return_value={"response": '{"commitments": []}'})
    return client

@pytest.fixture
def sample_transcript():
    return Transcript(
        meeting_id="m1",
        segments=[
            TranscriptSegment(segment_id="s1", speaker="Alice", text="I will finish the report by Friday."),
            TranscriptSegment(segment_id="s2", speaker="Bob", text="Sounds good. Let's meet at 2pm.")
        ]
    )

@pytest.mark.asyncio
async def test_extract_successfully(mock_ollama, sample_transcript):
    mock_ollama.generate = AsyncMock(return_value={
        "response": json.dumps({
            "commitments": [
                {
                    "segment_id": "s1",
                    "person": "Alice",
                    "commitment": "Finish the report",
                    "deadline": "Friday"
                }
            ]
        })
    })
    
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    
    assert len(commitments) == 1
    assert commitments[0].person == "Alice"
    assert commitments[0].commitment == "Finish the report"
    assert commitments[0].deadline == "Friday"
    
    # Check evidence
    assert commitments[0].evidence.segment_id == "s1"
    assert commitments[0].evidence.speaker == "Alice"
    assert commitments[0].evidence.text == "I will finish the report by Friday."

@pytest.mark.asyncio
async def test_extract_no_commitments(mock_ollama, sample_transcript):
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    assert len(commitments) == 0

@pytest.mark.asyncio
async def test_extract_multiple_commitments(mock_ollama, sample_transcript):
    mock_ollama.generate = AsyncMock(return_value={
        "response": json.dumps({
            "commitments": [
                {
                    "segment_id": "s1",
                    "person": "Alice",
                    "commitment": "Finish the report",
                    "deadline": "Friday"
                },
                {
                    "segment_id": "s2",
                    "person": "Bob",
                    "commitment": "Schedule the meeting"
                }
            ]
        })
    })
    
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    
    assert len(commitments) == 2

@pytest.mark.asyncio
async def test_extract_malformed_json(mock_ollama, sample_transcript):
    mock_ollama.generate = AsyncMock(return_value={"response": "invalid json"})
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    assert len(commitments) == 0

@pytest.mark.asyncio
async def test_extract_ollama_unavailable(mock_ollama, sample_transcript):
    mock_ollama.generate.side_effect = OllamaConnectionError("Connection failed")
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    assert len(commitments) == 0

@pytest.mark.asyncio
async def test_evidence_preserved_llm_hallucination(mock_ollama, sample_transcript):
    # If LLM hallucinates a segment_id that doesn't exist, it should be ignored
    mock_ollama.generate = AsyncMock(return_value={
        "response": json.dumps({
            "commitments": [
                {
                    "segment_id": "fake_id",
                    "person": "Alice",
                    "commitment": "Fake commitment"
                }
            ]
        })
    })
    extractor = CommitmentExtractor(ollama_client=mock_ollama)
    commitments = await extractor.extract_from_transcript(sample_transcript)
    assert len(commitments) == 0
