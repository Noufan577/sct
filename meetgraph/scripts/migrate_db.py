"""
Migration script: add new columns and tables to existing meetgraph.db
Safe to run multiple times (uses IF NOT EXISTS / TRY patterns).
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "meetgraph.db")
DB_PATH = os.path.abspath(DB_PATH)

print(f"Migrating: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# ---- 1. commitments: add new columns ----
existing_cols = {r[1] for r in cur.execute("PRAGMA table_info(commitments)")}
print(f"Existing commitment columns: {existing_cols}")

new_cols = {
    "original_deadline": "TEXT",
    "deadline_changed_at": "TEXT",
    "updated_at": "DATETIME",
}
for col, col_type in new_cols.items():
    if col not in existing_cols:
        cur.execute(f"ALTER TABLE commitments ADD COLUMN {col} {col_type}")
        print(f"  Added: commitments.{col}")
    else:
        print(f"  Already exists: commitments.{col}")

# Populate original_deadline from existing deadline for old rows
cur.execute("""
    UPDATE commitments
    SET original_deadline = deadline
    WHERE original_deadline IS NULL AND deadline IS NOT NULL
""")
print(f"  Backfilled original_deadline for {conn.total_changes} existing rows")

# ---- 2. Create commitment_status_history table ----
cur.execute("""
    CREATE TABLE IF NOT EXISTS commitment_status_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        commitment_id INTEGER NOT NULL REFERENCES commitments(id),
        old_status TEXT,
        new_status TEXT NOT NULL,
        changed_by TEXT,
        note TEXT,
        changed_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
""")
print("  commitment_status_history: created / already exists")

# Seed initial history for existing commitments that have no history
cur.execute("SELECT id, status, created_at FROM commitments")
rows = cur.fetchall()
for cid, status, created_at in rows:
    count = cur.execute(
        "SELECT COUNT(*) FROM commitment_status_history WHERE commitment_id = ?", (cid,)
    ).fetchone()[0]
    if count == 0:
        cur.execute("""
            INSERT INTO commitment_status_history (commitment_id, old_status, new_status, changed_by, note, changed_at)
            VALUES (?, NULL, ?, 'system', 'initial status on migration', ?)
        """, (cid, status, created_at))
        print(f"  Seeded history for commitment {cid}: {status}")

conn.commit()
conn.close()
print("Migration complete.")
