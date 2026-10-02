"""Bilingual recap generation (Phase 8).

Python (deterministic): gather timeline items, optionally filtered by
person. Ollama (semantic): render a recap + action list in the
requested language. Languages:
- en: English recap.
- ml: Malayalam (native script) recap.
- manglish: Malayalam written in Latin script (code-switched style
  common in Kerala meetings).

Falls back to an extractive English action list when the LLM is
unavailable. Evidence items always accompany the recap.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from app.integrations.ollama.client import OllamaClient
from app.integrations.ollama.exceptions import OllamaClientError

logger = logging.getLogger(__name__)

RECAP_LANGUAGES = ("en", "ml", "manglish")

LANGUAGE_INSTRUCTIONS = {
    "en": "Write the recap in English.",
    "ml": "Write the recap in Malayalam using Malayalam script.",
    "manglish": "Write the recap in Manglish: Malayalam written in Latin (English) script, "
    "freely mixing in English words, as spoken in Kerala offices.",
}

RECAP_SYSTEM_PROMPT = """You write short meeting-history recaps from evidence blocks.
Rules:
- Cover every commitment exactly once, in chronological order.
- State person, action, status and meeting for each.
- Do NOT invent people, actions, or meetings. If unsure, say so.
- Return ONLY valid JSON: {"recap": "<recap text>", "action_items": ["...", "..."]}"""


class RecapService:
    def __init__(self, ollama_client: Optional[OllamaClient] = None):
        self.client = ollama_client or OllamaClient()

    async def recap(
        self, items: List[Dict[str, Any]], language: str = "en"
    ) -> Dict[str, Any]:
        if language not in RECAP_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        if not items:
            return {
                "recap": "No meeting records to summarize.",
                "action_items": [],
                "cites": [],
                "fallback": True,
            }
        lines = []
        for i in items:
            lines.append(
                f"[#{i.get('commitment_id')}] {i.get('person')} — {i.get('commitment')} "
                f"(status: {i.get('status')}, meeting: {i.get('meeting_title')})"
            )
        prompt = (
            f"{LANGUAGE_INSTRUCTIONS[language]}\n\n"
            f"Commitments:\n" + "\n".join(lines) + "\n\nRecap as JSON."
        )
        try:
            response = await self.client.generate(
                prompt=prompt, system=RECAP_SYSTEM_PROMPT, format="json"
            )
            parsed = json.loads(response.get("response", ""))
            recap_text = str(parsed.get("recap", "")).strip()
            actions = parsed.get("action_items", [])
            if not recap_text or not isinstance(actions, list):
                raise ValueError("Incomplete recap from LLM")
            return {
                "recap": recap_text,
                "action_items": [str(a) for a in actions],
                "cites": items,
                "fallback": False,
            }
        except (OllamaClientError, ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
            logger.warning(f"Ollama recap failed, using fallback: {e}")
            actions = [
                f"{i.get('person')}: {i.get('commitment')} ({i.get('status')}, {i.get('meeting_title')})"
                for i in items
            ]
            return {
                "recap": "Meeting recap (extractive fallback):\n" + "\n".join(f"- {a}" for a in actions),
                "action_items": actions,
                "cites": items,
                "fallback": True,
            }
