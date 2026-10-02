"""Natural-language query over meeting history (Phase 5).

Split of responsibilities (per project rules):
- Python (deterministic): retrieve relevant commitments via token
  overlap, validate LLM citations, build fallback answers.
- Ollama (semantic): turn retrieved evidence into a natural-language
  answer. The LLM NEVER invents evidence: every citation is checked
  against the retrieved ids, and invalid cites are dropped. If Ollama
  is unavailable or returns garbage, a purely extractive fallback
  answer is built from the evidence alone.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.integrations.ollama.client import OllamaClient
from app.integrations.ollama.exceptions import OllamaClientError

logger = logging.getLogger(__name__)

STOPWORDS = frozenset(
    """
    what when where who whom whose which that this these those
    happened happens happen did does done do is was were are be been
    the a an to of in on for with about into over after before and or
    me my us our you your his her their its it s t me
    tell give show find status update progress any all how
    """.split()
)

QA_SYSTEM_PROMPT = """You answer questions about meeting history using ONLY the evidence blocks given to you.
Rules:
- Answer in the user's language (English unless asked otherwise).
- Base every claim on the evidence. Do NOT invent people, actions, dates, or meetings.
- If the evidence does not contain the answer, say so plainly.
- Refer to commitments by their id (e.g. #3) so the answer can be checked.
- Return ONLY valid JSON: {"answer": "<2-5 sentence answer>", "cites": [<commitment ids you used>]}"""


def tokenize(text: Any) -> List[str]:
    if not isinstance(text, str):
        return []
    return re.findall(r"[a-z0-9]+", text.lower())


def _item_text(item: Dict[str, Any]) -> str:
    ev = item.get("evidence") or {}
    parts = [
        item.get("person"),
        item.get("commitment"),
        item.get("status"),
        item.get("meeting_title"),
        ev.get("speaker"),
        ev.get("text"),
    ]
    return " ".join(p for p in parts if isinstance(p, str))


def retrieve(
    question: str,
    items: List[Dict[str, Any]],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """Deterministically rank commitments by token overlap with the
    question. Returns at most top_k items with score > 0, best first
    (ties broken chronologically)."""
    q_tokens = [t for t in tokenize(question) if t not in STOPWORDS]
    if not q_tokens:
        return []
    q_set = set(q_tokens)

    scored: List[Tuple[int, Dict[str, Any]]] = []
    for item in items:
        item_tokens = set(tokenize(_item_text(item))) - STOPWORDS
        score = len(q_set & item_tokens)
        # Boost when the question names the person directly.
        person_tokens = set(tokenize(item.get("person")))
        if person_tokens and person_tokens & q_set:
            score += 3
        if score > 0:
            scored.append((score, item))

    scored.sort(key=lambda s: (-s[0], s[1].get("meeting_created_at") or "", s[1].get("commitment_id") or 0))
    return [item for _, item in scored[: max(top_k, 1)]]


def build_context(items: List[Dict[str, Any]]) -> str:
    """Render retrieved commitments as numbered evidence blocks for the LLM."""
    lines = []
    for item in items:
        ev = item.get("evidence") or {}
        lines.append(
            f"[#{item.get('commitment_id')}] {item.get('person')} — {item.get('commitment')} "
            f"(status: {item.get('status')}, meeting: {item.get('meeting_title')} [{item.get('meeting_id')}])\n"
            f"    Said by {ev.get('speaker')}: \"{ev.get('text')}\""
        )
    return "\n".join(lines)


def fallback_answer(question: str, items: List[Dict[str, Any]]) -> Tuple[str, List[int]]:
    """Purely extractive answer built only from evidence (no LLM)."""
    if not items:
        return ("I don't have any meeting information about that.", [])
    lines = [f"Based on {len(items)} record(s) from meeting history:"]
    for item in items:
        lines.append(
            f"#{item.get('commitment_id')}: {item.get('person')} — {item.get('commitment')} "
            f"({item.get('status')}, {item.get('meeting_title')})."
        )
    return ("\n".join(lines), [i.get("commitment_id") for i in items])


class QAService:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.client = ollama_client or OllamaClient()

    async def answer(
        self,
        question: str,
        items: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> Dict[str, Any]:
        """Retrieve evidence for the question and generate a grounded
        answer. Returns {"answer", "cites" (evidence items), "fallback"}."""
        relevant = retrieve(question, items, top_k=top_k)
        if not relevant:
            text, _ = fallback_answer(question, [])
            return {"answer": text, "cites": [], "fallback": True}

        valid_ids = {i.get("commitment_id") for i in relevant}
        try:
            prompt = (
                f"Question: {question}\n\nEvidence:\n{build_context(relevant)}\n\n"
                "Answer as JSON."
            )
            response = await self.client.generate(
                prompt=prompt, system=QA_SYSTEM_PROMPT, format="json"
            )
            parsed = json.loads(response.get("response", ""))
            answer_text = str(parsed.get("answer", "")).strip()
            raw_cites = parsed.get("cites", [])
            if not isinstance(raw_cites, list):
                raw_cites = []
            cites = [c for c in raw_cites if isinstance(c, int) and c in valid_ids]
            if not answer_text:
                raise ValueError("Empty answer from LLM")
            by_id = {i.get("commitment_id"): i for i in relevant}
            cited_items = [by_id[c] for c in cites if c in by_id]
            if not cited_items:
                # LLM answered but cited nothing usable: attach everything
                # it was shown so the answer never ships without evidence.
                cited_items = relevant
            return {"answer": answer_text, "cites": cited_items, "fallback": False}
        except (OllamaClientError, ValueError, KeyError, TypeError, json.JSONDecodeError) as e:
            logger.warning(f"Ollama answer generation failed, using fallback: {e}")
            text, ids = fallback_answer(question, relevant)
            by_id = {i.get("commitment_id"): i for i in relevant}
            return {"answer": text, "cites": [by_id[i] for i in ids], "fallback": True}
