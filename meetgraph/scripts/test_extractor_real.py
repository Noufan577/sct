import asyncio
import os
import sys

# Add backend directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../backend')))

from app.services.extractor import CommitmentExtractor
from app.models.ingestion.transcript import Transcript, TranscriptSegment
from app.integrations.ollama.client import OllamaClient
from app.integrations.ollama.exceptions import OllamaConnectionError

async def main():
    print("Testing CommitmentExtractor against local Ollama...")
    client = OllamaClient()
    
    # Try a simple ping
    try:
        # Generate a simple completion to see if Ollama is alive
        await client.generate("Say hello", format="json")
    except OllamaConnectionError:
        print("Ollama is not running or not reachable at configured URL. Skipping real integration test.")
        return
    except Exception as e:
        print(f"Ollama reachable but encountered error: {e}")
    
    print("Ollama is reachable! Processing small transcript...")
    transcript = Transcript(
        meeting_id="meeting-test",
        segments=[
            TranscriptSegment(segment_id="s1", speaker="Alice", text="I'll finish the database migration by Friday."),
            TranscriptSegment(segment_id="s2", speaker="Bob", text="That sounds great. I'll review it over the weekend."),
            TranscriptSegment(segment_id="s3", speaker="Charlie", text="I don't have anything to do right now.")
        ]
    )
    
    extractor = CommitmentExtractor(ollama_client=client)
    commitments = await extractor.extract_from_transcript(transcript)
    
    print(f"Extracted {len(commitments)} commitments:")
    for c in commitments:
        print(f"- Person: {c.person}")
        print(f"  Commitment: {c.commitment}")
        print(f"  Deadline: {c.deadline}")
        print(f"  Evidence segment: {c.evidence.segment_id}")
        print(f"  Evidence text: '{c.evidence.text}'")

if __name__ == "__main__":
    asyncio.run(main())
