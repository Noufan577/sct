"""Wipe existing commitments and re-extract from Meetily using the improved
strict extractor.  Run AFTER restarting the server with the updated extractor.py.

Usage:
    python scripts/re_extract.py          # wipe + re-import all meetings
    python scripts/re_extract.py --keep   # keep old rows, only add new ones
"""
import urllib.request
import urllib.error
import json
import sys
import sqlite3
import os

BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8004")
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "meetgraph.db")
# Resolve to absolute path
DB_PATH = os.path.abspath(DB_PATH)


def api_get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None

def api_post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(
        f"{BASE}{path}", data=body,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        r = urllib.request.urlopen(req, timeout=600)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:400]}")
        return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None


def wipe_commitments():
    """Clear all commitment-related data from SQLite directly."""
    if not os.path.exists(DB_PATH):
        print(f"  DB not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Check tables exist
    c.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in c.fetchall()]

    wiped = 0
    if "commitment_status_history" in tables:
        c.execute("SELECT COUNT(*) FROM commitment_status_history")
        cnt = c.fetchone()[0]
        c.execute("DELETE FROM commitment_status_history")
        wiped += cnt
        print(f"  Wiped {cnt} status_history rows")

    if "commitments" in tables:
        c.execute("SELECT COUNT(*) FROM commitments")
        cnt = c.fetchone()[0]
        c.execute("DELETE FROM commitments")
        wiped += cnt
        print(f"  Wiped {cnt} commitment rows")

    conn.commit()
    conn.close()
    return wiped > 0


def main():
    keep = "--keep" in sys.argv

    print("=== MeetGraph Re-Extraction (Strict) ===")
    print(f"  DB path: {DB_PATH}")

    if not keep:
        print("\n1. Wiping old commitments...")
        wipe_commitments()
    else:
        print("\n1. Keeping existing commitments (--keep mode)")

    # 2. Check sync status
    print("\n2. Checking Meetily sync status...")
    sync = api_get("/api/sync/status")
    if not sync:
        print("  ERROR: Cannot reach sync endpoint. Is the server running?")
        sys.exit(1)

    print(f"  Found {len(sync)} meetings in Meetily")
    for m in sync:
        print(f"  - {m.get('title') or m['id']} (fetched: {m['fetched']})")

    # 3. Re-import each meeting (Ollama extraction happens server-side)
    print("\n3. Re-importing meetings with STRICT extractor...")
    total_commitments = 0
    for m in sync:
        mid = m["id"]
        print(f"\n  Importing: {mid}")
        result = api_post(f"/api/sync/meetings/{mid}")
        if result:
            found = result.get("commitments_found", 0)
            total_commitments += found
            print(f"  -> commitments_found: {found}")
        else:
            print("  -> Import failed or no new commitments")

    # 4. Verify results
    print(f"\n4. Verification: {total_commitments} total commitments extracted")
    commits = api_get("/api/timeline")
    if commits is not None:
        total_items = sum(g["item_count"] for g in commits)
        print(f"  Timeline threads: {len(commits)}, total items: {total_items}")
        for g in commits:
            print(f"  [{g['thread_id']}] {g['person']} — {g['topic'][:60]}")

    # 5. Show the actual commitments for review
    print("\n5. Final commitment list:")
    conn = sqlite3.connect(DB_PATH)
    for row in conn.execute(
        "SELECT id, person, commitment, status, evidence_text FROM commitments ORDER BY id"
    ):
        cid, person, text, status, evidence = row
        print(f"  [{cid}] {person}: {text} ({status})")
        print(f"       Evidence: {evidence[:100]}...")
    conn.close()

    print(f"\n=== Done — {total_commitments} commitments from {len(sync)} meetings ===")


if __name__ == "__main__":
    main()
