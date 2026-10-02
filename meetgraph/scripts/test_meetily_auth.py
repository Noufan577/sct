import urllib.request
import json

KEY = "MIUyRAiIJB7BOvh9EPw2qqMi17B6pl6l7bNNxB2a_pc"
req = urllib.request.Request(
    "http://127.0.0.1:8420/v1/meetings",
    headers={"Authorization": f"Bearer {KEY}"}
)

try:
    with urllib.request.urlopen(req, timeout=10) as response:
        print("Status code:", response.status)
        data = json.loads(response.read().decode())
        print("Response keys:", list(data.keys()) if isinstance(data, dict) else len(data))
        if isinstance(data, dict) and "meetings" in data:
            print("Number of meetings:", len(data["meetings"]))
            for m in data["meetings"][:5]:
                print(f" - [{m.get('id')}] {m.get('title')}")
        else:
            print("Data:", data)
except Exception as e:
    print("Error:", e)
    if hasattr(e, 'read'):
        print("Error body:", e.read().decode())
