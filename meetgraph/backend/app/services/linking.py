"""Cross-meeting commitment linking (Phase 4).

Deterministic, local-first grouping of commitments across meetings.
LLM is NOT used here: matching is pure Python (person normalization +
text similarity), so links are reproducible and never invent evidence.

A "link group" connects commitments made by the same person whose
wording is similar enough to be plausibly the same action tracked
across meetings (e.g. committed in meeting 1, still open in meeting 2,
completed in meeting 3).
"""

import re
from difflib import SequenceMatcher
from typing import Any, Dict, List

# Minimum similarity (0-1) for two commitment texts to be linked.
LINK_THRESHOLD = 0.5

# Allowed lifecycle statuses for a commitment.
# PROPOSED -> COMMITTED -> OPEN -> DONE/SLIPPED
# COMPLETED is kept as a UI-friendly alias for DONE.
COMMITMENT_STATUSES = ("PROPOSED", "COMMITTED", "OPEN", "DONE", "SLIPPED", "COMPLETED")


def normalize_person(name: Any) -> str:
    """Normalize a person name for comparison: lowercase, trimmed,
    collapsed whitespace. Non-strings become ''."""
    if not isinstance(name, str):
        return ""
    return re.sub(r"\s+", " ", name.strip().lower())


def normalize_text(text: Any) -> str:
    """Normalize commitment text for comparison: lowercase, punctuation
    removed, collapsed whitespace."""
    if not isinstance(text, str):
        return ""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return re.sub(r"\s+", " ", cleaned).strip()


def similarity(a: str, b: str) -> float:
    """Deterministic text similarity in [0, 1] on normalized inputs."""
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    return SequenceMatcher(None, na, nb).ratio()


def _commitment_sort_key(item: Dict[str, Any]):
    return (item.get("meeting_created_at") or "", item.get("commitment_id") or 0)


def build_timeline(
    commitments: List[Dict[str, Any]],
    threshold: float = LINK_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Group flat commitment dicts into cross-meeting link groups.

    Each input dict must have: commitment_id, person, commitment,
    status, meeting_id (meetily id), meeting_title, meeting_created_at,
    evidence (dict with speaker/timestamp/text/segment_id).

    Returns groups ordered by earliest item; items within a group are
    chronological. Group ids are stable for a given input ordering
    ("thread-1", "thread-2", ...).
    """
    # Union-find over indices.
    parent = list(range(len(commitments)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    for i in range(len(commitments)):
        for j in range(i + 1, len(commitments)):
            ci, cj = commitments[i], commitments[j]
            if normalize_person(ci.get("person")) != normalize_person(cj.get("person")):
                continue
            if not normalize_person(ci.get("person")):
                continue
            if similarity(ci.get("commitment"), cj.get("commitment")) >= threshold:
                union(i, j)

    groups: Dict[int, List[Dict[str, Any]]] = {}
    for idx, item in enumerate(commitments):
        groups.setdefault(find(idx), []).append(item)

    ordered = sorted(groups.values(), key=lambda items: _commitment_sort_key(min(items, key=_commitment_sort_key)))
    for items in ordered:
        items.sort(key=_commitment_sort_key)

    result = []
    for n, items in enumerate(ordered, start=1):
        first = items[0]
        result.append(
            {
                "thread_id": f"thread-{n}",
                "person": first.get("person") or "Unknown",
                "topic": first.get("commitment") or "",
                "meeting_count": len({i.get("meeting_id") for i in items}),
                "item_count": len(items),
                "items": items,
            }
        )
    return result
