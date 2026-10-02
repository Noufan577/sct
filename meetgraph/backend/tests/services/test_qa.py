import json
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.qa import retrieve, fallback_answer, QAService
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
        _item(1, "Rahul", "Prepare the budget report", meeting="m1", status="COMMITTED"),
        _item(2, "Rahul", "Prepare budget report for Q3", meeting="m2", status="OPEN"),
        _item(3, "Priya", "Book flight tickets to Delhi", meeting="m2", status="COMMITTED"),
    ]


def test_retrieve_finds_relevant(items):
    found = retrieve("What happened to Rahul's action?", items)
    ids = [i["commitment_id"] for i in found]
    assert 1 in ids and 2 in ids
    assert 3 not in ids


def test_retrieve_no_match(items):
    assert retrieve("What is the weather on Mars?", items) == []


def test_retrieve_empty_question(items):
    assert retrieve("what is the?", items) == []


def test_fallback_answer_empty():
    text, cites = fallback_answer("anything", [])
    assert "don't have" in text
    assert cites == []


def test_fallback_answer_extractive(items):
    text, cites = fallback_answer("q", items[:2])
    assert "Prepare the budget report" in text
    assert cites == [1, 2]


@pytest.mark.asyncio
async def test_answer_uses_llm_and_validates_cites(items):
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({"answer": "Rahul committed and it is still open.", "cites": [1, 2, 999]})
    })
    result = await QAService(ollama_client=mock).answer("What happened to the budget report?", items)
    assert result["fallback"] is False
    assert "Rahul" in result["answer"]
    # Hallucinated cite 999 must be dropped
    assert [i["commitment_id"] for i in result["cites"]] == [1, 2]


@pytest.mark.asyncio
async def test_answer_ignores_malformed_cites(items):
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({"answer": "Rahul did the budget report.", "cites": [[1], "x", 2, None]})
    })
    result = await QAService(ollama_client=mock).answer("budget report Rahul", items)
    assert result["fallback"] is False
    assert [i["commitment_id"] for i in result["cites"]] == [2]


@pytest.mark.asyncio
async def test_answer_attaches_evidence_when_llm_cites_nothing(items):
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={
        "response": json.dumps({"answer": "Rahul did the budget report.", "cites": []})
    })
    result = await QAService(ollama_client=mock).answer("budget report Rahul", items)
    assert result["fallback"] is False
    assert len(result["cites"]) > 0


@pytest.mark.asyncio
async def test_answer_falls_back_when_ollama_down(items):
    mock = MagicMock()
    mock.generate = AsyncMock(side_effect=OllamaConnectionError("down"))
    result = await QAService(ollama_client=mock).answer("What happened to Rahul?", items)
    assert result["fallback"] is True
    assert "budget report" in result["answer"].lower()
    assert len(result["cites"]) > 0


@pytest.mark.asyncio
async def test_answer_falls_back_on_garbage_json(items):
    mock = MagicMock()
    mock.generate = AsyncMock(return_value={"response": "not json"})
    result = await QAService(ollama_client=mock).answer("What happened?", items)
    assert result["fallback"] is True


@pytest.mark.asyncio
async def test_answer_no_evidence(items):
    mock = MagicMock()
    result = await QAService(ollama_client=mock).answer("Weather on Mars?", items)
    assert "don't have" in result["answer"]
    assert result["cites"] == []
    mock.generate.assert_not_called()
