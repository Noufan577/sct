import sqlite3
import os

path = os.path.expandvars(r"%APPDATA%\pro.meetily.ai\meeting_minutes.sqlite")
print("Opening:", path)
conn = sqlite3.connect(path)
cur = conn.cursor()

cur.execute("UPDATE gateway_consumers SET enabled = 1 WHERE name = 'hack'")
print("Rows updated for hack:", cur.rowcount)

conn.commit()

# Verify
cur.execute("SELECT id, name, enabled FROM gateway_consumers")
for row in cur.fetchall():
    print("Consumer:", row)

conn.close()
