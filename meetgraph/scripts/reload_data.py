"""Re-import all meetings from Meetily to fix Unknown speaker identities and
populate the new schema columns (original_deadline, status_history)."""
import urllib.request
import urllib.error
import json
import sys

import os
BASE = os.getenv("API_BASE_URL", "http://127.0.0.1:8004")

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
        r = urllib.request.urlopen(req, timeout=600)  # extraction can take time
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:400]}")
        return None
    except Exception as e:
        print(f"  Request error: {e}")
        return None

print("=== MeetGraph Data Reload ===")

# 1. Check sync status
print("\n1. Checking Meetily sync status...")
sync = api_get("/api/sync/status")
if not sync:
    print("  ERROR: Cannot reach sync endpoint")
    sys.exit(1)

print(f"  Found {len(sync)} meetings in Meetily")
for m in sync:
    print(f"  - {m['title'] or m['id']} (fetched: {m['fetched']})")

# 2. Re-import each meeting (idempotent)
print("\n2. Re-importing meetings (will deduplicate commitments)...")
for m in sync:
    mid = m['id']
    print(f"\n  Importing: {mid}")
    result = api_post(f"/api/sync/meetings/{mid}")
    if result:
        print(f"  -> commitments_found: {result.get('commitments_found', 0)}")
    else:
        print("  -> Import failed or no new commitments")

# 3. Check speaker identities
print("\n3. Checking speaker identities...")
ids = api_get("/api/identities")
if ids is not None:
    print(f"  Total identities: {len(ids)}")
    for i in ids:
        print(f"  - [{i['meetily_id'][:20]}] {i['speaker_label']} => {i['person_name']} (conf={i['confidence']:.2f}, method={i['method']}, confirmed={i['confirmed']})")

# 4. Check commitments
print("\n4. Checking commitments...")
commits = api_get("/api/timeline")
if commits is not None:
    total = sum(g['item_count'] for g in commits)
    print(f"  Timeline threads: {len(commits)}, total items: {total}")
    for g in commits:
        print(f"  Thread [{g['thread_id']}]: {g['person']} — {g['topic'][:50]}")

# 5. Test new intel endpoints
print("\n5. Testing drift report...")
drift = api_get("/api/intel/drift")
if drift is not None:
    print(f"  Drift items: {len(drift)}")

print("\n6. Testing since endpoint...")
if sync and len(sync) > 0:
    first_mid = sync[0]['id']
    since = api_get(f"/api/intel/since/{first_mid}")
    if since:
        print(f"  Changes since {first_mid}: new={len(since.get('new', []))}, status_changes={len(since.get('status_changes', []))}, slipped={len(since.get('slipped', []))}")

print("\n=== Done ===")
