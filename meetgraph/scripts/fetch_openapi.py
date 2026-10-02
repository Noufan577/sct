import urllib.request
import json
import os

token = os.getenv("MEETILY_API_KEY", "")
url = "http://127.0.0.1:8420/openapi.json"
os.makedirs('data/meetily', exist_ok=True)

try:
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"Bearer {token}")
    response = urllib.request.urlopen(req)
    data = json.loads(response.read().decode('utf-8'))
    with open('data/meetily/openapi.json', 'w') as f:
        json.dump(data, f, indent=2)
    print("OpenAPI spec saved successfully with Bearer token.")
except Exception as e:
    print(f"Bearer failed: {e}")
    try:
        req = urllib.request.Request(url)
        req.add_header("X-API-Key", token)
        response = urllib.request.urlopen(req)
        data = json.loads(response.read().decode('utf-8'))
        with open('data/meetily/openapi.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("OpenAPI spec saved successfully with X-API-Key.")
    except Exception as e2:
        print(f"X-API-Key failed: {e2}")
