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
import json
import logging
from typing import Any, Dict, List, Optional
from app.integrations.ollama.client import OllamaClient

logger = logging.getLogger(__name__)

SELF_INTRO = re.compile(r"\b(?i:i am|i'm|this is|my name is|it'?s)\s+([A-Z][a-z]{2,})\b")
ADDRESSED = re.compile(r"\b([A-Z][a-z]{2,}),\s")
COMMON = {"Yes", "Yeah", "Sure", "Okay", "Thanks", "Thank", "Sorry", "Please", "Good", "Hello", "Hi", "Hey", "Welcome", "Okay,"}

async def resolve_speakers(
    segments: List[Dict[str, Any]], 
    prior_confirmed: Optional[Dict[str, str]] = None,
    ollama_client: Optional[OllamaClient] = None,
) -> Dict[str, Dict[str, Any]]:
    prior_confirmed = prior_confirmed or {}
    dialogue: Dict[str, str] = {}
    
    # Build a chronological script for the LLM
    script_lines = []
    for seg in segments:
        label = seg.get("speaker")
        if not label: continue
        text = seg.get("text") or ""
        dialogue.setdefault(label, "")
        dialogue[label] += " " + text
        script_lines.append(f"{label}: {text}")

    result: Dict[str, Dict[str, Any]] = {}
    unresolved_labels = set()

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
            
        # (a) Regex self-introduction
        for seg in segments:
            if seg.get("speaker") != label: continue
            hits = SELF_INTRO.findall(seg.get("text") or "")
            if hits:
                result[label] = {
                    "person": hits[0],
                    "confidence": 0.8,
                    "evidence_segment_id": seg.get("id"),
                    "evidence_text": (seg.get("text") or "")[:120],
                    "method": "regex_self_intro",
                }
                break
        if label in result: continue
        
        # (b) Addressed by name
        for seg in segments:
            if seg.get("speaker") == label: continue
            hits = [h for h in ADDRESSED.findall(seg.get("text") or "") if h not in COMMON]
            if hits:
                result[label] = {
                    "person": hits[0],
                    "confidence": 0.5,
                    "evidence_segment_id": seg.get("id"),
                    "evidence_text": (seg.get("text") or "")[:120],
                    "method": "regex_addressed_by_name",
                }
                break
        if label not in result:
            unresolved_labels.add(label)

    # 3. Behavioral Inference using LLM for unresolved speakers
    if unresolved_labels and ollama_client:
        script_snippet = "\n".join(script_lines[:150]) # First ~150 lines should cover most context
        
        system_prompt = (
            "You are a master semantic identity resolver. Read the following meeting script. "
            "By analyzing how tasks are assigned, how people answer questions directed at specific names, "
            "and other behavioral cues, deduce the real names of the speaker labels.\n"
            "Return ONLY a raw JSON object mapping the speaker label to their real name. "
            "Example: {\"Speaker 1\": \"Rahul\", \"Speaker 2\": \"Priya\"}\n"
            "If you cannot confidently determine a name, DO NOT include that speaker in the JSON."
        )
        
        try:
            llm_res = await ollama_client.generate(prompt=script_snippet, system=system_prompt, format="json")
            inferred_map = json.loads(llm_res.get("response", "{}"))
            
            for label in unresolved_labels:
                if label in inferred_map:
                    result[label] = {
                        "person": inferred_map[label],
                        "confidence": 0.75,
                        "evidence_segment_id": None,
                        "evidence_text": "Semantic/Behavioral inference via LLM",
                        "method": "llm_semantic_inference",
                    }
                else:
                    result[label] = {
                        "person": label,
                        "confidence": 0.0,
                        "evidence_segment_id": None,
                        "evidence_text": None,
                        "method": "unresolved",
                    }
        except Exception as e:
            logger.warning(f"LLM Speaker Resolution failed: {e}")
            for label in unresolved_labels:
                result[label] = {
                    "person": label,
                    "confidence": 0.0,
                    "evidence_segment_id": None,
                    "evidence_text": None,
                    "method": "unresolved",
                }
    else:
        for label in unresolved_labels:
            result[label] = {
                "person": label,
                "confidence": 0.0,
                "evidence_segment_id": None,
                "evidence_text": None,
                "method": "unresolved",
            }
            
    return result
