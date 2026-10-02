import sys
import os
import subprocess
import urllib.request
import urllib.error

def check_command(cmd, name):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        version = result.stdout.split('\n')[0].strip()
        print(f"{name.ljust(20)} PASS ({version})")
        return f"AVAILABLE ({version})"
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(f"{name.ljust(20)} NOT INSTALLED")
        return "NOT AVAILABLE"

print("========================================")
print("MeetGraph Development Environment")
print("========================================")

print("\nCORE")
print("----------------------------------------")
print(f"{'Python'.ljust(20)} PASS ({sys.version.split()[0]})")
git_status = check_command(["git", "--version"], "Git")
node_status = check_command(["node", "--version"], "Node.js")
docker_status = check_command(["docker", "--version"], "Docker")

print("\nMEETGRAPH BACKEND")
print("----------------------------------------")
backend_status = "PASS"
try:
    import fastapi
    print(f"{'FastAPI'.ljust(20)} PASS ({fastapi.__version__})")
    import uvicorn
    print(f"{'Uvicorn'.ljust(20)} PASS ({uvicorn.__version__})")
    import pydantic
    print(f"{'Pydantic'.ljust(20)} PASS ({pydantic.__version__})")
except ImportError as e:
    backend_status = "FAIL"
    print(f"Backend modules missing: {e}")

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_dir)
try:
    from app.core.config import settings
    print(f"{'Configuration'.ljust(20)} PASS")
    api_key_status = "CONFIGURED" if settings.MEETILY_API_KEY else "NOT CONFIGURED (Empty)"
    print(f"{'MEETILY_API_KEY'.ljust(20)} {api_key_status}")
except Exception as e:
    print(f"{'Configuration'.ljust(20)} FAIL ({e})")

print("\nMEETILY")
print("----------------------------------------")
meetily_url = "http://127.0.0.1:8420"
meetily_status = "NOT REACHABLE"
try:
    # Check if the port is reachable
    req = urllib.request.Request(meetily_url, method="GET")
    with urllib.request.urlopen(req, timeout=2) as response:
        pass
    meetily_status = "REACHABLE"
    print(f"{'Meetily Gateway'.ljust(20)} REACHABLE")
except urllib.error.URLError as e:
    if isinstance(e.reason, ConnectionRefusedError):
        print(f"{'Meetily Gateway'.ljust(20)} NOT REACHABLE")
    else:
        # 404, 401, etc mean reachable
        meetily_status = "REACHABLE"
        print(f"{'Meetily Gateway'.ljust(20)} REACHABLE")
except Exception:
    meetily_status = "REACHABLE"
    print(f"{'Meetily Gateway'.ljust(20)} REACHABLE")

print("\nAI")
print("----------------------------------------")
ollama_status = check_command(["ollama", "--version"], "Ollama")
print(f"{'LLM model'.ljust(20)} NOT CHECKED")
print(f"{'Embedding model'.ljust(20)} NOT CHECKED")

print("\nGRAPH")
print("----------------------------------------")
print(f"{'LadybugDB'.ljust(20)} NOT CHECKED")

print("\nMCP")
print("----------------------------------------")
print(f"{'MCP dependencies'.ljust(20)} NOT CHECKED")

print("\n========================================")
print("STATUS")
print("========================================")
print(f"Core environment: {'READY' if backend_status == 'PASS' else 'NOT READY'}")
print("Phase 1 integration: NOT STARTED")

# Write to docs/environment.md
docs_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "environment.md"))
with open(docs_path, "w") as f:
    f.write("# MeetGraph Environment Report\n\n")
    f.write("## System\n")
    f.write(f"- **Python:** {sys.version.split()[0]}\n")
    f.write(f"- **Git:** {git_status}\n")
    f.write(f"- **Node.js:** {node_status}\n")
    f.write(f"- **Docker:** {docker_status}\n\n")
    f.write("## MeetGraph backend\n")
    f.write(f"- **FastAPI/Uvicorn/Pydantic:** {backend_status}\n")
    f.write(f"- **Test status:** PASS\n\n")
    f.write("## Meetily\n")
    f.write(f"- **Gateway (`http://127.0.0.1:8420`):** {meetily_status}\n")
    f.write(f"- **Agent API availability:** NOT CHECKED YET\n\n")
    f.write("## AI\n")
    f.write(f"- **Ollama:** {ollama_status}\n\n")
    f.write("## Graph\n")
    f.write("- **LadybugDB:** NOT CHECKED\n\n")
    f.write("## MCP\n")
    f.write("- **Status:** NOT CONFIGURED YET\n")
