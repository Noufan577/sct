"""Seed the hackathon demo scenario (idempotent — safe to re-run).

Meeting 1: Rahul commits to an action.
Meeting 2: the action is still open (code-switched Manglish evidence).
Meeting 3: the action is completed.
Plus one unrelated commitment as a decoy.

Run from the meetgraph/ directory so DATABASE_URL resolves to ./meetgraph.db:
    backend\\.venv\\Scripts\\python scripts\\seed_demo.py
"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../backend")))

from app.db.database import init_db, SessionLocal
from app.models.domain.commitment import Commitment, Evidence
from app.repositories.db_repository import DBRepository


def C(person, text, status, speaker, ts, quote, deadline=None):
    return Commitment(
        person=person,
        commitment=text,
        deadline=deadline,
        status=status,
        evidence=Evidence(
            meeting_id="",
            segment_id="demo-seed",
            speaker=speaker,
            timestamp=ts,
            text=quote,
        ),
    )


SCENARIO = [
    ("demo-m1", "Sprint planning", [
        C("Rahul", "Prepare the budget report", "COMMITTED", "Rahul", 12.5,
          "I will prepare the budget report by Friday.", deadline="Friday"),
        C("Priya", "Book flight tickets to Delhi", "COMMITTED", "Priya", 45.0,
          "I will book the flight tickets today."),
    ]),
    ("demo-m2", "Mid-sprint check", [
        C("Rahul", "Prepare budget report for Q3", "OPEN", "Rahul", 8.0,
          "Budget report almost done aanu, oru correction bakki undu, will finish soon."),
    ]),
    ("demo-m3", "Sprint review", [
        C("Rahul", "Prepare the budget report", "COMPLETED", "Rahul", 20.0,
          "The budget report is done, shared with the team."),
    ]),
]


def main():
    init_db()
    db = SessionLocal()
    repo = DBRepository(db)
    for meetily_id, title, commitments in SCENARIO:
        for c in commitments:
            c.evidence.meeting_id = meetily_id
        repo.save_meeting(meetily_id, title=title)
        saved = repo.save_commitments(meetily_id, commitments)
        print(f"{meetily_id} ({title}): {len(saved)} new commitment(s)")
    total = len(repo.get_all_commitments())
    print(f"Total commitments in DB: {total}")
    db.close()


if __name__ == "__main__":
    main()
