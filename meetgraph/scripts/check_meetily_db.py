import sqlite3
import json
import os

path = os.path.expandvars(r"%APPDATA%\pro.meetily.ai\meeting_minutes.sqlite")
print("Opening:", path)
conn = sqlite3.connect(path)
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print("Tables:", tables)

for t in tables:
    if any(k in t.lower() for k in ["api", "key", "token", "gateway", "consumer", "client", "setting", "integration"]):
        print(f"\n--- Table: {t} ---")
        cur.execute(f"PRAGMA table_info({t})")
        cols = cur.fetchall()
        print("Columns:", [c[1] for c in cols])
        cur.execute(f"SELECT * FROM {t} LIMIT 5")
        rows = cur.fetchall()
        print("Rows:", rows)

conn.close()
