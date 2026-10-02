import urllib.request
import urllib.error
import os

token = os.getenv("MEETILY_API_KEY", "")
url = "http://127.0.0.1:8420/openapi.json"

methods = [
    ("Bearer", {"Authorization": f"Bearer {token}"}),
    ("Token", {"Authorization": f"Token {token}"}),
    ("Header_x_api_key", {"x-api-key": token}),
    ("Header_Api_Key", {"Api-Key": token}),
]

for name, headers in methods:
    try:
        req = urllib.request.Request(url, headers=headers)
        response = urllib.request.urlopen(req)
        print(f"Success with {name}: {response.getcode()}")
        break
    except urllib.error.HTTPError as e:
        print(f"{name} failed with {e.code}: {e.read().decode('utf-8', errors='ignore')}")
    except Exception as e:
        print(f"{name} error: {e}")
