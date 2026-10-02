import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.recap import RecapService
from app.integrations.ollama.exceptions import OllamaConnectionError


def _item(cid, person, text, meeting="m1", status="COMMITTED"):
    return {
        "commitment_id": cid,
        "person": person,
        "commitment": text,
        "deadline": None,
        "status": status,
        "meeting_id": meeting,
        "meeting_title": f"Title {meeting}",
        "meeting_created_at": f"2026-01-0{cid}T00:00:00",
        "evidence": {"speaker": person, "timestamp": 1.0, "text": text, "segment_id": f"s{cid}"},
    }


@pytest.fixture
def items():
    return [
        _item(1, "Rahul", "Prepare the budget report", meeting="m1", status="COMPLETED"),
        _item(2, "Priya", "Book flight tickets", meeting="m1", status="OPEN"),
    ]


def _mock_ok(recap="Recap text", actions=None):
    m = MagicMock()
    m.generate = AsyncMock(return_value={
        "response": json.dumps({
            "recap": recap,
            "action_items": actions if actions is not None else ["a1", "a2"],
        })
    })
    return m


@pytest.mark.asyncio
async def test_recap_english(items):
    result = await RecapService(ollama_client=_mock_ok()).recap(items, language="en")
    assert result["fallback"] is False
    assert result["recap"] == "Recap text"
    assert result["action_items"] == ["a1", "a2"]
    assert len(result["cites"]) == 2


@pytest.mark.asyncio
async def test_recap_language_passed_to_prompt(items):
    mock = _mock_ok()
    await RecapService(ollama_client=mock).recap(items, language="manglish")
    _, kwargs = mock.generate.call_args
    assert "Manglish" in kwargs["prompt"] or "manglish" in kwargs["prompt"].lower()


@pytest.mark.asyncio
async def test_recap_bad_language(items):
    with pytest.raises(ValueError):
        await RecapService(ollama_client=_mock_ok()).recap(items, language="klingon")


@pytest.mark.asyncio
async def test_recap_empty_items():
    result = await RecapService(ollama_client=_mock_ok()).recap([], language="ml")
    assert "No meeting records" in result["recap"]
    assert result["cites"] == []


@pytest.mark.asyncio
async def test_recap_fallback_on_ollama_down(items):
    mock = MagicMock()
    mock.generate = AsyncMock(side_effect=OllamaConnectionError("down"))
    result = await RecapService(ollama_client=mock).recap(items, language="ml")
    assert result["fallback"] is True
    assert "budget report" in result["recap"].lower()
    assert len(result["cites"]) == 2
