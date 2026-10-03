"""Completion Detector — Cross-Meeting Auto-Resolution.

When a new meeting is processed, this service scans the transcript for
signals that a previously open commitment has been completed.

Examples of completion signals:
- "The report is done / finished / submitted / ready"
- "I've completed the analysis"
- "I sent the email yesterday"
- "Jessica informed me the work is done"

The detector matches these signals to open commitments from past meetings
using person identity + topic similarity, and auto-updates their status to
COMPLETED in the database (commitments, history, graph).
"""

import re
import logging
from typing import Any, Dict, List, Optional
from difflib import SequenceMatcher
from sqlalchemy.orm import Session
from app.db.models import CommitmentModel, CommitmentStatusHistory, MeetingModel
from app.services.linking import normalize_person, normalize_text, similarity
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Regex patterns that signal work completion
DONE_SIGNALS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"\b(is|are|was|were|has been|have been|getting it|got it)\s+(done|finished|completed|submitted|delivered|ready|sent|deployed|published)\b",
        r"\b(i'?ve?|we'?ve?|i have|we have|i|we)\s+(done|finished|completed|complete|submitted|delivered|sent|deployed)\b",
        r"\b(already|just)\s+(done|finished|completed|complete|submitted|sent|delivered)\b",
        r"\b(finished|completed|complete|done|submitted|delivered|sent)\s+(the|it|this|that|my|our)\b",
        r"\bwork\s+is\s+(done|complete|finished)\b",
        r"\breport\s+(is|was)\s+(ready|done|complete|finished|submitted)\b",
        r"\b(task|assignment|job)\s+(is|was)\s+(done|complete|finished)\b",
        r"\blet.{0,15}know.{0,30}(done|finished|completed|complete|submitted)\b",
        r"\binform(ing|ed)?.{0,20}(done|finished|completed|complete|submitted)\b",
        r"\bgetting.{0,10}done\b",
        r"\bgot.{0,10}done\b",
    ]
]

# Minimum text similarity to match a completion signal to an open commitment
COMPLETION_LINK_THRESHOLD = 0.35


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from text for topic matching."""
    normalized = normalize_text(text)
    # Remove stopwords
    stopwords = {"the", "a", "an", "is", "are", "was", "were", "have", "has", "had",
                 "be", "been", "being", "do", "does", "did", "will", "would", "could",
                 "should", "may", "might", "shall", "and", "or", "but", "in", "on",
                 "at", "to", "for", "of", "with", "by", "from", "up", "about", "into",
                 "it", "its", "my", "your", "his", "her", "our", "their", "this", "that"}
    words = set(normalized.split())
    return words - stopwords


def _topic_matches(signal_text: str, commitment_text: str) -> float:
    """Check if the completion signal's topic matches a commitment's topic.
    Uses both sequence similarity and keyword overlap."""
    seq_sim = similarity(signal_text, commitment_text)
    
    kw_signal = _extract_keywords(signal_text)
    kw_commit = _extract_keywords(commitment_text)
    
    if kw_signal and kw_commit:
        overlap = len(kw_signal & kw_commit) / len(kw_commit)
    else:
        overlap = 0.0
    
    return max(seq_sim, overlap)


def detect_completions(
    segments: List[Dict[str, Any]],
    open_commitments: List[CommitmentModel],
    resolved_speaker_map: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Scan transcript segments for completion signals and match them
    against open commitments.
    
    Returns a list of matches:
      {"commitment_id": int, "commitment_text": str, "person": str,
       "segment_id": str, "signal_text": str, "score": float}
    """
    completions = []
    
    for i, seg in enumerate(segments):
        text = seg.get("text", "") or ""
        
        # Check if this segment contains a completion signal
        is_signal = any(p.search(text) for p in DONE_SIGNALS)
        if not is_signal:
            continue
        
        # Determine who is speaking (resolved name)
        raw_speaker = seg.get("speaker", "")
        speaker_name = resolved_speaker_map.get(raw_speaker, raw_speaker)
        
        # Gather context (last 15 segments + current) to resolve pronouns and implicit subjects
        # A conversation about a topic can easily span 15-20 short sentences before the "it's done"
        context_segments = segments[max(0, i-15):i+1]
        context_text = " ".join(s.get("text", "") for s in context_segments if s.get("text"))
        
        # Try to match against open commitments
        for commitment in open_commitments:
            if commitment.status in ("DONE", "COMPLETED"):
                continue
            
            # Check person match
            commit_person = normalize_person(commitment.person)
            seg_person = normalize_person(speaker_name)
            
            # Match if: same person is speaking, OR the person's name is mentioned in context
            person_match = (commit_person == seg_person) or (commit_person in normalize_text(context_text))
            
            if not person_match:
                continue
            
            # Check topic similarity against the wider context, not just the "it's done" line
            score = _topic_matches(context_text, commitment.commitment)
            
            if score >= COMPLETION_LINK_THRESHOLD:
                completions.append({
                    "commitment_id": commitment.id,
                    "commitment_text": commitment.commitment,
                    "person": commitment.person,
                    "segment_id": seg.get("id", ""),
                    "signal_text": text,
                    "score": score,
                })
                logger.info(
                    f"Auto-completion detected: '{commitment.person}' -> "
                    f"'{commitment.commitment}' (score={score:.2f}, signal='{text[:80]}')"
                )
    
    return completions


def apply_completions(
    db: Session,
    completions: List[Dict[str, Any]],
    meeting_id: str
) -> int:
    """Apply detected completions to the database.
    Returns the number of commitments marked as COMPLETED."""
    
    count = 0
    for match in completions:
        commitment = db.query(CommitmentModel).filter(
            CommitmentModel.id == match["commitment_id"]
        ).first()
        
        if not commitment or commitment.status in ("DONE", "COMPLETED"):
            continue
        
        old_status = commitment.status
        commitment.status = "COMPLETED"
        commitment.updated_at = datetime.now(timezone.utc)
        
        # Record in audit history
        hist = CommitmentStatusHistory(
            commitment_id=commitment.id,
            old_status=old_status,
            new_status="COMPLETED",
            changed_by="auto_completion_detector",
            note=(
                f"Auto-detected as complete in meeting {meeting_id}. "
                f"Signal: '{match['signal_text'][:100]}' (score={match['score']:.2f})"
            ),
            changed_at=datetime.now(timezone.utc),
        )
        db.add(hist)
        count += 1
        logger.info(f"Marked commitment {commitment.id} ('{commitment.commitment}') as COMPLETED")
    
    if count > 0:
        db.commit()
    
    return count
