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
    ("demo-m1", "Project Kickoff", [
        C("Rahul", "Set up the initial code repository", "COMMITTED", "Rahul", 10.0,
          "I'm Rahul, I will set up the initial code repository by tomorrow.", deadline="Tomorrow"),
        C("Priya", "Draft the UI mockups", "COMMITTED", "Priya", 25.0,
          "I'll start drafting the UI mockups in Figma today."),
    ]),
    ("demo-m2", "Design Sync", [
        C("Priya", "Finalize the color palette", "COMMITTED", "Priya", 5.0,
          "I will finalize the color palette this evening."),
        C("Rahul", "Set up the initial code repository", "OPEN", "Rahul", 45.0,
          "Repo structure setup is almost done aanu, just pushing it now."),
    ]),
    ("demo-m3", "Architecture Review", [
        C("Rahul", "Set up the initial code repository", "COMPLETED", "Rahul", 12.0,
          "The repository is live and access is granted to everyone."),
        C("Arjun", "Provision the AWS database", "COMMITTED", "Arjun", 30.0,
          "This is Arjun, I'll provision the AWS database for our backend."),
    ]),
    ("demo-m4", "Mid-week Standup", [
        C("Priya", "Draft the UI mockups", "COMPLETED", "Priya", 15.0,
          "Mockups are finished and ready for review."),
        C("Arjun", "Provision the AWS database", "OPEN", "Arjun", 22.0,
          "Database creation in progress, waiting for IAM permissions."),
    ]),
    ("demo-m5", "Bug Bash Planning", [
        C("Rahul", "Fix the login authentication bug", "COMMITTED", "Rahul", 40.0,
          "I will fix the login authentication bug before Friday."),
        C("Arjun", "Provision the AWS database", "COMPLETED", "Arjun", 55.0,
          "AWS DB is finally up and running, credentials shared."),
    ]),
    ("demo-m6", "Pre-Launch Sync", [
        C("Priya", "Prepare the slide deck for demo", "COMMITTED", "Priya", 18.0,
          "I'll prepare the slide deck for the hackathon demo."),
        C("Rahul", "Fix the login authentication bug", "OPEN", "Rahul", 33.0,
          "Login bug fixing start cheythu, it should be done tonight."),
    ]),
    ("demo-m7", "Hackathon Go-Live", [
        C("Rahul", "Fix the login authentication bug", "COMPLETED", "Rahul", 5.0,
          "Login bug is fully resolved. We are good to go!"),
        C("Priya", "Prepare the slide deck for demo", "COMPLETED", "Priya", 10.0,
          "Slide deck is complete. Let's win this!"),
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
