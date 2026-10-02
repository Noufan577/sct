import urllib.request

for port in [8000, 8001, 8002, 8003, 8004]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as r:
            print(f"Port {port}: {r.status} {r.read().decode()}")
    except Exception as e:
        print(f"Port {port}: {e}")
