from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.db.models import MeetingModel, CommitmentModel, CommitmentStatusHistory
from app.models.domain.commitment import Commitment, Evidence

# All valid lifecycle statuses for a commitment.
COMMITMENT_STATUSES = ("PROPOSED", "COMMITTED", "OPEN", "DONE", "SLIPPED", "COMPLETED")


def _now():
    return datetime.now(timezone.utc)


class DBRepository:
    def __init__(self, db: Session):
        self.db = db

    # ─────────────────────────── Meetings ────────────────────────────

    def save_meeting(self, meetily_id: str, title: str = None) -> MeetingModel:
        """Save a meeting to the database. Returns existing if it already exists."""
        meeting = self.get_meeting(meetily_id)
        if meeting:
            return meeting

        meeting = MeetingModel(meetily_id=meetily_id, title=title)
        self.db.add(meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def get_meeting(self, meetily_id: str) -> Optional[MeetingModel]:
        """Retrieve a meeting by its Meetily ID."""
        return (
            self.db.query(MeetingModel)
            .filter(MeetingModel.meetily_id == meetily_id)
            .first()
        )

    # ─────────────────────────── Commitments ─────────────────────────

    def save_commitments(self, meetily_id: str, commitments: List[Commitment]) -> List[CommitmentModel]:
        """Save a list of extracted commitments to the database. Prevents exact duplicates.
        Automatically records the initial status in status_history.
        """
        meeting = self.get_meeting(meetily_id)
        if not meeting:
            raise ValueError(f"Meeting {meetily_id} not found in database.")

        saved_models = []
        for c in commitments:
            # Simple deduplication check
            existing = (
                self.db.query(CommitmentModel)
                .filter(
                    CommitmentModel.meeting_id == meeting.id,
                    CommitmentModel.person == c.person,
                    CommitmentModel.commitment == c.commitment,
                )
                .first()
            )

            if existing:
                continue

            model = CommitmentModel(
                meeting_id=meeting.id,
                person=c.person,
                commitment=c.commitment,
                deadline=c.deadline,
                original_deadline=c.deadline,   # Capture original deadline on first save
                status=c.status,
                created_at=_now(),
                updated_at=_now(),
                evidence_segment_id=c.evidence.segment_id,
                evidence_speaker=c.evidence.speaker,
                evidence_timestamp=c.evidence.timestamp,
                evidence_text=c.evidence.text,
            )
            self.db.add(model)
            self.db.flush()   # Get the id before adding history

            # Record initial status in history
            hist = CommitmentStatusHistory(
                commitment_id=model.id,
                old_status=None,
                new_status=c.status,
                changed_by="extractor",
                note=f"Extracted from meeting {meetily_id}",
                changed_at=_now(),
            )
            self.db.add(hist)
            saved_models.append(model)

        if saved_models:
            self.db.commit()

        for m in saved_models:
            self.db.refresh(m)

        return saved_models

    def get_commitments(self, meetily_id: str) -> List[CommitmentModel]:
        """Retrieve all commitments for a given meeting."""
        meeting = self.get_meeting(meetily_id)
        if not meeting:
            return []
        return (
            self.db.query(CommitmentModel)
            .filter(CommitmentModel.meeting_id == meeting.id)
            .all()
        )

    def get_all_commitments(self) -> List[Dict[str, Any]]:
        """Retrieve every commitment with its meeting info, flattened for
        cross-meeting linking. Ordered chronologically."""
        rows = (
            self.db.query(CommitmentModel, MeetingModel)
            .join(MeetingModel, CommitmentModel.meeting_id == MeetingModel.id)
            .order_by(MeetingModel.created_at, MeetingModel.id, CommitmentModel.id)
            .all()
        )
        result = []
        for c, m in rows:
            result.append(
                {
                    "commitment_id": c.id,
                    "person": c.person,
                    "commitment": c.commitment,
                    "deadline": c.deadline,
                    "original_deadline": c.original_deadline,
                    "deadline_changed_at": c.deadline_changed_at,
                    "status": c.status,
                    "meeting_id": m.meetily_id,
                    "meeting_title": m.title,
                    "meeting_created_at": m.created_at.isoformat() if m.created_at else "",
                    "evidence": {
                        "speaker": c.evidence_speaker,
                        "timestamp": c.evidence_timestamp,
                        "text": c.evidence_text,
                        "segment_id": c.evidence_segment_id,
                    },
                }
            )
        return result

    def update_commitment_status(
        self, commitment_id: int, status: str, changed_by: str = "user", note: str = None
    ) -> Optional[CommitmentModel]:
        """Update a commitment's lifecycle status and record in history.
        Returns the updated row, or None if the id does not exist."""
        commitment = (
            self.db.query(CommitmentModel)
            .filter(CommitmentModel.id == commitment_id)
            .first()
        )
        if not commitment:
            return None
        old_status = commitment.status
        commitment.status = status
        commitment.updated_at = _now()

        hist = CommitmentStatusHistory(
            commitment_id=commitment_id,
            old_status=old_status,
            new_status=status,
            changed_by=changed_by,
            note=note,
            changed_at=_now(),
        )
        self.db.add(hist)
        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def update_commitment_deadline(
        self, commitment_id: int, new_deadline: str, meeting_id: str = None
    ) -> Optional[CommitmentModel]:
        """Update the current deadline and record the meeting where it changed.
        original_deadline is never touched after first save.
        """
        commitment = (
            self.db.query(CommitmentModel)
            .filter(CommitmentModel.id == commitment_id)
            .first()
        )
        if not commitment:
            return None

        commitment.deadline = new_deadline
        commitment.deadline_changed_at = meeting_id
        commitment.updated_at = _now()

        # Auto-transition to SLIPPED if deadline changed and status is COMMITTED or OPEN
        if commitment.status in ("COMMITTED", "OPEN") and commitment.original_deadline and new_deadline != commitment.original_deadline:
            old_status = commitment.status
            commitment.status = "SLIPPED"
            hist = CommitmentStatusHistory(
                commitment_id=commitment_id,
                old_status=old_status,
                new_status="SLIPPED",
                changed_by="system",
                note=f"Deadline changed from {commitment.original_deadline} to {new_deadline}",
                changed_at=_now(),
            )
            self.db.add(hist)

        self.db.commit()
        self.db.refresh(commitment)
        return commitment

    def get_status_history(self, commitment_id: int) -> List[Dict[str, Any]]:
        """Return full status audit trail for a commitment."""
        rows = (
            self.db.query(CommitmentStatusHistory)
            .filter(CommitmentStatusHistory.commitment_id == commitment_id)
            .order_by(CommitmentStatusHistory.changed_at)
            .all()
        )
        return [
            {
                "id": r.id,
                "old_status": r.old_status,
                "new_status": r.new_status,
                "changed_by": r.changed_by,
                "note": r.note,
                "changed_at": r.changed_at.isoformat() if r.changed_at else None,
            }
            for r in rows
        ]

    def get_drift_report(self) -> List[Dict[str, Any]]:
        """Return all commitments that have a changed deadline (drift)."""
        rows = (
            self.db.query(CommitmentModel, MeetingModel)
            .join(MeetingModel, CommitmentModel.meeting_id == MeetingModel.id)
            .filter(
                CommitmentModel.original_deadline != None,
                CommitmentModel.deadline != CommitmentModel.original_deadline,
            )
            .all()
        )
        result = []
        for c, m in rows:
            result.append(
                {
                    "commitment_id": c.id,
                    "person": c.person,
                    "commitment": c.commitment,
                    "original_deadline": c.original_deadline,
                    "current_deadline": c.deadline,
                    "status": c.status,
                    "meeting_id": m.meetily_id,
                    "meeting_title": m.title,
                    "deadline_changed_at_meeting": c.deadline_changed_at,
                }
            )
        return result

    def get_changes_since(self, since_meeting_id: str) -> Dict[str, Any]:
        """Get commitments that changed since a specific meeting.
        Returns new commitments, status changes, and slipped deadlines.
        """
        since_meeting = self.get_meeting(since_meeting_id)
        if not since_meeting:
            return {"new": [], "status_changes": [], "slipped": []}

        since_dt = since_meeting.created_at

        # New commitments from meetings after since_dt
        new_rows = (
            self.db.query(CommitmentModel, MeetingModel)
            .join(MeetingModel, CommitmentModel.meeting_id == MeetingModel.id)
            .filter(MeetingModel.created_at > since_dt)
            .all()
        )
        new_commits = [
            {
                "commitment_id": c.id,
                "person": c.person,
                "commitment": c.commitment,
                "deadline": c.deadline,
                "status": c.status,
                "meeting_title": m.title,
                "meeting_id": m.meetily_id,
            }
            for c, m in new_rows
        ]

        # Status changes recorded after since_dt
        status_rows = (
            self.db.query(CommitmentStatusHistory, CommitmentModel)
            .join(CommitmentModel, CommitmentStatusHistory.commitment_id == CommitmentModel.id)
            .filter(CommitmentStatusHistory.changed_at > since_dt)
            .filter(CommitmentStatusHistory.old_status != None)
            .all()
        )
        status_changes = [
            {
                "commitment_id": h.commitment_id,
                "commitment": c.commitment,
                "person": c.person,
                "old_status": h.old_status,
                "new_status": h.new_status,
                "changed_at": h.changed_at.isoformat() if h.changed_at else None,
                "note": h.note,
            }
            for h, c in status_rows
        ]

        # Slipped deadlines
        slipped = [
            sc for sc in status_changes if sc["new_status"] == "SLIPPED"
        ]

        return {
            "since_meeting": since_meeting_id,
            "new": new_commits,
            "status_changes": [s for s in status_changes if s["new_status"] != "SLIPPED"],
            "slipped": slipped,
        }

    # ─────────────────────────── Speaker Identities ──────────────────

    def get_confirmed_identity_map(self) -> Dict[str, str]:
        """speaker_label -> person for all confirmed mappings (reused globally)."""
        from app.db.models import SpeakerIdentityModel  # noqa

        rows = (
            self.db.query(SpeakerIdentityModel)
            .filter(SpeakerIdentityModel.confirmed == 1)
            .all()
        )
        mapping: Dict[str, str] = {}
        for r in rows:
            if r.speaker_label not in mapping:
                mapping[r.speaker_label] = r.person_name
        return mapping

    def get_confirmed_person_names(self) -> set:
        """Return the set of all person names that have ever been confirmed globally.
        Used for cross-meeting merging: if a new meeting resolves a speaker to a name
        that matches a previously confirmed person, we treat them as the same node.
        """
        from app.db.models import SpeakerIdentityModel  # noqa

        rows = (
            self.db.query(SpeakerIdentityModel.person_name)
            .filter(SpeakerIdentityModel.confirmed == 1)
            .distinct()
            .all()
        )
        return {r.person_name for r in rows if r.person_name}

    def get_open_commitments(self, exclude_meeting_id: Optional[str] = None) -> List:
        """Return all commitments that are not yet DONE/COMPLETED.
        Optionally exclude commitments from the current meeting being processed.
        Used by the completion detector to find what to auto-resolve."""
        q = (
            self.db.query(CommitmentModel)
            .join(MeetingModel, CommitmentModel.meeting_id == MeetingModel.id)
            .filter(CommitmentModel.status.notin_(["DONE", "COMPLETED"]))
        )
        if exclude_meeting_id:
            q = q.filter(MeetingModel.meetily_id != exclude_meeting_id)
        return q.all()

    def save_speaker_identities(self, meetily_id: str, mapping: Dict[str, Dict[str, Any]]) -> List:
        """Upsert resolver output. Confirmed rows are never overwritten."""
        from app.db.models import SpeakerIdentityModel  # noqa

        saved = []
        for label, info in mapping.items():
            existing = (
                self.db.query(SpeakerIdentityModel)
                .filter(
                    SpeakerIdentityModel.meetily_id == meetily_id,
                    SpeakerIdentityModel.speaker_label == label,
                )
                .first()
            )
            if existing and existing.confirmed:
                saved.append(existing)
                continue
            if not existing:
                existing = SpeakerIdentityModel(
                    meetily_id=meetily_id,
                    speaker_label=label,
                    person_name=info["person"],
                )
                self.db.add(existing)
            existing.person_name = info["person"]
            existing.confidence = info.get("confidence", 0.0)
            existing.evidence_segment_id = info.get("evidence_segment_id")
            existing.evidence_text = info.get("evidence_text")
            existing.method = info.get("method")
            saved.append(existing)

        self.db.commit()
        for r in saved:
            self.db.refresh(r)
        return saved

    def list_speaker_identities(self, meetily_id: Optional[str] = None) -> List:
        from app.db.models import SpeakerIdentityModel  # noqa

        q = self.db.query(SpeakerIdentityModel)
        if meetily_id:
            q = q.filter(SpeakerIdentityModel.meetily_id == meetily_id)
        return q.all()

    def confirm_speaker_identity(self, identity_id: int, person_name: str) -> Optional[object]:
        """Manual confirmation: set confirmed=1, propagate globally to all speaker
        identity rows AND retroactively rewrite all commitments that still reference
        the old label so the graph/timeline immediately show the correct name."""
        from app.db.models import SpeakerIdentityModel  # noqa

        row = (
            self.db.query(SpeakerIdentityModel)
            .filter(SpeakerIdentityModel.id == identity_id)
            .first()
        )
        if not row:
            return None

        old_label = row.speaker_label   # e.g. "Speaker 20" or "20"
        old_name  = row.person_name     # e.g. "Speaker 20" (unresolved)

        row.person_name = person_name
        row.confirmed   = 1
        row.method      = "manual_confirm"

        # 1. Propagate to all other identity rows with same speaker_label
        others = (
            self.db.query(SpeakerIdentityModel)
            .filter(SpeakerIdentityModel.speaker_label == old_label)
            .all()
        )
        for o in others:
            if o.id == identity_id:
                continue
            o.person_name = person_name
            o.confidence  = max(o.confidence or 0.0, 0.9)
            o.method      = "confirmed_reuse"
            o.confirmed   = 1

        # 2. Retroactively rewrite commitments where person OR evidence_speaker
        #    still holds the old label or old unresolved name.
        labels_to_replace = {old_label, old_name}
        if old_label.startswith("Speaker "):
            # e.g. "Speaker 20" -> also match raw "20"
            labels_to_replace.add(old_label.split(" ", 1)[1])
        else:
            # numeric string -> also match "Speaker {N}"
            labels_to_replace.add(f"Speaker {old_label}")

        commitments_updated = 0
        for lbl in labels_to_replace:
            rows_p = (
                self.db.query(CommitmentModel)
                .filter(CommitmentModel.person == lbl)
                .all()
            )
            for c in rows_p:
                c.person = person_name
                c.updated_at = _now()
                commitments_updated += 1

            rows_e = (
                self.db.query(CommitmentModel)
                .filter(CommitmentModel.evidence_speaker == lbl)
                .all()
            )
            for c in rows_e:
                c.evidence_speaker = person_name
                commitments_updated += 1

        self.db.commit()
        self.db.refresh(row)
        return row
