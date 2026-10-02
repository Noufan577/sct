import urllib.request, json

BASE = 'http://127.0.0.1:8004'

def get(path):
    try:
        r = urllib.request.urlopen(BASE + path, timeout=15)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        return {'error': e.code, 'body': body}
    except Exception as e:
        return {'error': str(e)}

def post(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(BASE + path, data=body,
        headers={'Content-Type': 'application/json'}, method='POST')
    try:
        r = urllib.request.urlopen(req, timeout=60)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        return {'error': e.code, 'body': body}
    except Exception as e:
        return {'error': str(e)}

def patch(path, data=None):
    body = json.dumps(data or {}).encode()
    req = urllib.request.Request(BASE + path, data=body,
        headers={'Content-Type': 'application/json'}, method='PATCH')
    try:
        r = urllib.request.urlopen(req, timeout=30)
        return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        return {'error': e.code, 'body': body}
    except Exception as e:
        return {'error': str(e)}

OK = lambda v: "OK" if not isinstance(v, dict) or 'error' not in v else "FAIL: " + str(v.get('body', v.get('error')))[:100]

print("=== FINAL MeetGraph API Test Suite ===\n")

print("1. Health:", OK(get('/health')))

ts = get('/api/timeline')
print("2. Timeline:", OK(ts), f"- {len(ts)} threads" if isinstance(ts, list) else "")
if isinstance(ts, list):
    for g in ts:
        for item in g.get('items', []):
            print(f"   person={item.get('person')} deadline={item.get('deadline')} orig={item.get('original_deadline')} status={item.get('status')}")

drift = get('/api/intel/drift')
print("3. Drift:", OK(drift), f"- {len(drift)} items")

history = get('/api/intel/commitments/1/history')
print("4. Status History #1:", OK(history), f"- {len(history) if isinstance(history, list) else '?'} records")
if isinstance(history, list):
    for h in history:
        print(f"   {h.get('changed_at','?')[:16]}: {h.get('old_status','?')} -> {h.get('new_status')} by {h.get('changed_by')}")

brief = get('/api/intel/brief/meeting-c9c2f66f-a822-441d-81dc-6cee98024460')
print("5. Pre-meeting Brief:", OK(brief), f"- open={brief.get('open_count',0)} slipped={brief.get('slipped_count',0)}" if 'open_count' in brief else "")

since = get('/api/intel/since/meeting-9438640c-7ff2-4b92-93bf-672e60910804')
print("6. Since:", OK(since), f"- new={len(since.get('new',[]))}" if 'new' in since else "")

# Test status update with audit trail
print("7. Update commitment #1 to OPEN:")
upd = patch('/api/intel/commitments/1/status', {'status': 'OPEN', 'note': 'Following up'})
print("   ", OK(upd), upd.get('status',''))

history_after = get('/api/intel/commitments/1/history')
print("8. History after update:", OK(history_after), f"- {len(history_after) if isinstance(history_after, list) else '?'} records")
if isinstance(history_after, list):
    for h in history_after:
        print(f"   {h.get('changed_at','?')[:16]}: {h.get('old_status','?')} -> {h.get('new_status')} by {h.get('changed_by')}")

meetings = get('/api/meetings')
print("9. Meetings:", OK(meetings), f"- {len(meetings)}" if isinstance(meetings, list) else "")

ids = get('/api/identities')
print("10. Identities:", OK(ids), f"- {len(ids)}" if isinstance(ids, list) else "")

print("\n=== All core API tests complete ===")
