import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), '..', 'meetgraph.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', [t[0] for t in tables])

for table_name in [t[0] for t in tables]:
    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = cur.fetchone()[0]
    print(f"  {table_name}: {count} rows")
    if count > 0 and count <= 5:
        cur.execute(f"SELECT * FROM {table_name}")
        rows = cur.fetchall()
        cur.execute(f"PRAGMA table_info({table_name})")
        cols = [c[1] for c in cur.fetchall()]
        print(f"    cols: {cols}")
        for row in rows:
            print(f"    {row}")

conn.close()
