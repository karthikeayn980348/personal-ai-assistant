# Personal AI Assistant — Version 1

A local Windows prototype with chat, projects, document extraction, editable memory, starter coding-pattern detection, and writing-style analysis.

## Requirements
- Python 3.11+
- An OpenAI API key for live AI responses (API usage may cost money; ask a parent or guardian before enabling billing).

## Windows setup
Open PowerShell in the project folder:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
notepad .env
```

Put your API key in `.env`. The sample model is `gpt-4.1-mini`; replace it with a model enabled for your API account if needed. Never commit `.env` or share your API key.

## Run
Open two PowerShell windows in the project folder and activate `.venv` in both.

Backend:
```powershell
uvicorn backend.main:app --reload
```

Frontend:
```powershell
streamlit run frontend/app.py
```

Open the Streamlit URL shown in the terminal. Backend health: http://127.0.0.1:8000/health . API docs: http://127.0.0.1:8000/docs .

## Current features
- Project-based chat history
- TXT, Markdown, PDF, DOCX, and code file extraction
- Explicitly saved and deletable memory
- Basic Python pattern detection and occurrence counters
- Writing sample analysis

## Current limitations
This is an early local prototype, not a production-ready secure app. Memory is explicit rather than automatically inferred. Code checks are a small rule set, not a complete static analyzer. Scanned-PDF OCR, web research, authentication, encryption, sandboxed code execution, desktop packaging, and advanced task execution are not included yet. Do not upload passwords, private keys, financial details, medical records, or other sensitive data.

## Architecture
Streamlit UI → FastAPI backend → OpenAI Responses API + SQLite + document extraction. Coding analysis is a separate module intended to grow into deeper static analysis and personalized debugging support.