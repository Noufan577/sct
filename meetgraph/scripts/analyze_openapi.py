import json
import urllib.request
import os

with open('data/meetily/openapi.json', 'r') as f:
    spec = json.load(f)

print(f"OpenAPI Version: {spec.get('openapi')}")
print(f"Title: {spec.get('info', {}).get('title')}")
print(f"Version: {spec.get('info', {}).get('version')}")

endpoints = []
for path, path_item in spec.get('paths', {}).items():
    for method, operation in path_item.items():
        if method.lower() not in ['get', 'post', 'put', 'patch', 'delete']:
            continue
        endpoints.append((method.upper(), path, operation.get('summary', '')))

print("\nRelevant Endpoints:")
for method, path, summary in endpoints:
    if 'meeting' in path.lower() or 'transcript' in path.lower() or 'summar' in path.lower():
        print(f"{method} {path} - {summary}")

# Also try to fetch one meeting to create a fixture
print("\nFetching meeting list...")
token = os.getenv("MEETILY_API_KEY", "")
headers = {"Authorization": f"Bearer {token}"}
base_url = "http://127.0.0.1:8420"

try:
    req = urllib.request.Request(f"{base_url}/v1/meetings", headers=headers)
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    meetings = data.get('meetings', [])
    print(f"Meetings retrieved: {len(meetings)}")
    if meetings:
        meeting_id = meetings[0].get('id')
        print(f"Fetching transcript for meeting {meeting_id}...")
        try:
            treq = urllib.request.Request(f"{base_url}/v1/meetings/{meeting_id}/transcript", headers=headers)
            tresp = urllib.request.urlopen(treq)
            transcript_data = json.loads(tresp.read().decode('utf-8'))
            
            # Save fixture safely (dummy text)
            os.makedirs('backend/tests/fixtures/meetily', exist_ok=True)
            safe_transcript = []
            segments = transcript_data.get('segments', [])
            for seg in segments:
                safe_seg = {
                    "speaker": seg.get('speaker', 'Speaker'),
                    "text": "[REDACTED]",
                    "start": seg.get('timestamp'),
                    "duration": seg.get('duration')
                }
                if 'id' in seg: safe_seg['id'] = seg['id']
                safe_transcript.append(safe_seg)
                
            with open('backend/tests/fixtures/meetily/transcript_sample.json', 'w') as f:
                json.dump(safe_transcript, f, indent=2)
            print(f"Transcript fixture saved with {len(safe_transcript)} segments!")
        except Exception as e:
            print(f"Transcript fetch failed: {e}")
            
except Exception as e:
    print(f"Meeting fetch failed: {e}")
