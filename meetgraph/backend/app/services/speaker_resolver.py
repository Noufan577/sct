"""Speaker Identity Resolver (increment 1).

Meetily only labels speakers ("Speaker 1", "Unknown"). This resolver
maps those labels to real people using safe evidence only:
a) the speaker introduces themselves ("I'm Rahul", "This is Arjun")
b) another speaker addresses them by name ("Thanks, Rahul", "Arjun, ...")
c) a previously CONFIRMED mapping for the same speaker label

Low-confidence results keep the original label — never guess.
Confirmed mappings persist globally and are reused in future meetings.
"""

import re
from typing import Any, Dict, List, Optional

SELF_INTRO = re.compile(
    r"\b(?i:i am|i'm|this is|my name is|it'?s)\s+([A-Z][a-z]{2,})\b"
)
ADDRESSED = re.compile(r"\b([A-Z][a-z]{2,}),\s")
COMMON = {
    "Yes", "Yeah", "Sure", "Okay", "Thanks", "Thank", "Sorry", "Please",
    "Good", "Hello", "Hi", "Hey", "Welcome", "Okay,",
}


def _candidates_from_text(text: str) -> List[str]:
    found = []
    found += SELF_INTRO.findall(text or "")
    for m in ADDRESSED.findall(text or ""):
        if m not in COMMON:
            found.append(m)
    return found


def resolve_speakers(
    segments: List[Dict[str, Any]], prior_confirmed: Optional[Dict[str, str]] = None
) -> Dict[str, Dict[str, Any]]:
    """segments: raw segments with {id, speaker, text}.
    Returns {speaker_label: {"person", "confidence", "evidence_segment_id",
    "evidence_text", "method"}}."""
    prior_confirmed = prior_confirmed or {}
    dialogue: Dict[str, str] = {}
    for seg in segments:
        label = seg.get("speaker")
        if not label:
            continue
        dialogue.setdefault(label, "")
        dialogue[label] += " " + (seg.get("text") or "")

    result: Dict[str, Dict[str, Any]] = {}
    for label, text in dialogue.items():
        if label in prior_confirmed:
            result[label] = {
                "person": prior_confirmed[label],
                "confidence": 1.0,
                "evidence_segment_id": None,
                "evidence_text": "previously confirmed",
                "method": "confirmed_reuse",
            }
            continue
        # (a) self-introduction inside this speaker's own lines
        for seg in segments:
            if seg.get("speaker") != label:
                continue
            hits = SELF_INTRO.findall(seg.get("text") or "")
            if hits:
                result[label] = {
                    "person": hits[0],
                    "confidence": 0.8,
                    "evidence_segment_id": seg.get("id"),
                    "evidence_text": (seg.get("text") or "")[:120],
                    "method": "self_intro",
                }
                break
        if label in result:
            continue
        # (b) addressed by name in OTHER speakers' lines
        for seg in segments:
            if seg.get("speaker") == label:
                continue
            hits = [h for h in ADDRESSED.findall(seg.get("text") or "") if h not in COMMON]
            if hits:
                result[label] = {
                    "person": hits[0],
                    "confidence": 0.5,
                    "evidence_segment_id": seg.get("id"),
                    "evidence_text": (seg.get("text") or "")[:120],
                    "method": "addressed_by_name",
                }
                break
        if label not in result:
            # Unknown is not a person; keep the safe original label.
            result[label] = {
                "person": label,
                "confidence": 0.0,
                "evidence_segment_id": None,
                "evidence_text": None,
                "method": "unresolved",
            }
    return result
