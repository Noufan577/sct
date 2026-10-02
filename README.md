# SCT — MeetGraph

**MeetGraph** is a local-first, evidence-backed commitment and decision memory layer for **Meetily**.

It tracks commitments, deadlines, decisions, and speaker identities across multiple meetings, providing an interactive timeline, relationship graph, deadline drift detection, multi-language audio recap/transcription, and an evidence-backed Q&A interface.

---

## 🚀 Key Features

- **Meetily Integration**: Live sync with Meetily Pro gateway for meeting metadata and transcripts.
- **Commitment Extraction**: AI-driven task and commitment extraction with exact quote evidence and timestamps.
- **Speaker Resolution**: Resolves speaker labels (`Speaker 1`, `Speaker 2`) to real person names using dialogue self-introductions and cross-speaker address cues.
- **Deadline Drift Detection**: Tracks commitment deadline slips across chronological meetings (`original_deadline` vs `current_deadline`).
- **Cross-Meeting Timeline & Graph**: Visual threads of commitments per person and interactive force-directed graph.
- **Audio Transcription & Recap**: Multi-language support (English, Malayalam, Manglish) via Sarvam AI & local Ollama models.
- **Evidence-Backed Q&A**: Hybrid query engine returning answers backed by verifiable verbatim quotes.

---

## 🛠️ Tech Stack

- **Backend**: FastAPI, SQLAlchemy, SQLite, Uvicorn, HTTPX
- **AI / LLM**: Ollama (`qwen3:4b`), Sarvam AI API
- **Frontend**: Clean Vanilla JS, CSS3 Design System with Light/Dark mode and i18n
- **Integrations**: Meetily Pro Local Gateway (`127.0.0.1:8420`)

---

## 🏃 Running Locally

### 1. Backend & Web App
```bash
cd meetgraph/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8004
```
Access the application at [http://127.0.0.1:8004](http://127.0.0.1:8004).

### 2. Meetily Sync & Reload
```bash
python meetgraph/scripts/reload_data.py
```
