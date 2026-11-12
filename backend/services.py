import os
import re
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv
from pypdf import PdfReader
from docx import Document as DocxDocument

load_dotenv()
SYSTEM_PROMPT = """You are a personal productivity and learning assistant. Be accurate, direct, and transparent about uncertainty. Do not claim a task is complete unless you actually completed it. Use the user's saved preferences only when relevant. For code, explain causes simply and preserve the user's apparent skill level and style. Do not invent personal experiences or facts about the user."""

def ai_response(user_text: str, context: str = "") -> str:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key or key == "put_your_api_key_here":
        return "AI is not connected yet. Add your API key to .env and restart the backend. Your message was received."
    client = OpenAI(api_key=key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    prompt = f"{SYSTEM_PROMPT}\n\nRelevant context:\n{context[:12000]}\n\nUser request:\n{user_text}"
    response = client.responses.create(model=model, input=prompt)
    return response.output_text or "The model returned an empty response."

def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv"}:
        return path.read_text(encoding="utf-8", errors="replace")
    if suffix == ".pdf":
        return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    if suffix == ".docx":
        return "\n".join(p.text for p in DocxDocument(str(path)).paragraphs)
    raise ValueError("Supported files: TXT, MD, PDF, DOCX, PY, JS, TS, HTML, CSS, JSON, CSV.")

def detect_code_patterns(code: str, language: str = "python"):
    findings = []
    if language.lower() == "python":
        if re.search(r"for\s+\w+\s+in\s+range\(\s*len\(", code):
            findings.append(("index-based-loop", "A loop uses range(len(...)); direct iteration may be simpler."))
        if re.search(r"while\s+True\s*:", code) and "break" not in code:
            findings.append(("while-true-no-break", "A while True loop has no visible break statement. Check that it can stop."))
        if re.search(r"=\s*input\(", code) and not re.search(r"\bint\s*\(", code):
            findings.append(("input-type-check", "input() returns text. Convert it if you need a number and handle invalid input."))
        if re.search(r"if\s+\w+\s*=\s*", code):
            findings.append(("assignment-in-condition", "A single '=' appears in an if condition; Python comparisons normally use '=='."))
    return findings
