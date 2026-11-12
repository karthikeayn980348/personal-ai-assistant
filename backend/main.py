from pathlib import Path
import uuid
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel, Field
from backend.db import init_db, connect, UPLOAD_DIR
from backend.services import ai_response, extract_text, detect_code_patterns

app = FastAPI(title="Personal AI Assistant API", version="0.1.0")

@app.on_event("startup")
def startup():
    init_db()

class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    project_id: int | None = None
class MemoryIn(BaseModel):
    category: str = "preference"
    content: str = Field(min_length=1, max_length=2000)
class CodeIn(BaseModel):
    code: str = Field(min_length=1, max_length=20000)
    language: str = "python"
class StyleIn(BaseModel):
    sample: str = Field(min_length=30, max_length=12000)

@app.get("/health")
def health():
    return {"status": "ok", "version": "0.1.0"}

@app.get("/projects")
def list_projects():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM projects ORDER BY id DESC").fetchall()]

@app.post("/projects")
def create_project(item: ProjectIn):
    with connect() as db:
        cur = db.execute("INSERT INTO projects(name, description) VALUES (?, ?)", (item.name, item.description))
        return {"id": cur.lastrowid, "name": item.name, "description": item.description}

@app.delete("/projects/{project_id}")
def delete_project(project_id: int):
    with connect() as db:
        if not db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
        db.execute("DELETE FROM projects WHERE id=?", (project_id,))
        db.execute("DELETE FROM messages WHERE project_id=?", (project_id,))
        db.execute("DELETE FROM documents WHERE project_id=?", (project_id,))
    return {"deleted": True}

def project_context(project_id):
    if project_id is None:
        return ""
    with connect() as db:
        docs = db.execute("SELECT filename, extracted_text FROM documents WHERE project_id=? ORDER BY id DESC LIMIT 5", (project_id,)).fetchall()
        memories = db.execute("SELECT category, content FROM memories ORDER BY id DESC LIMIT 20").fetchall()
        patterns = db.execute("SELECT language, pattern, occurrences FROM mistake_patterns ORDER BY occurrences DESC LIMIT 10").fetchall()
    parts = [f"Document {d['filename']}:\n{d['extracted_text'][:2500]}" for d in docs]
    if memories: parts.append("Saved user memories:\n" + "\n".join(f"- [{m['category']}] {m['content']}" for m in memories))
    if patterns: parts.append("Recorded code patterns:\n" + "\n".join(f"- {p['language']}: {p['pattern']} ({p['occurrences']} observations)" for p in patterns))
    return "\n\n".join(parts)

@app.post("/chat")
def chat(item: ChatIn):
    answer = ai_response(item.message, project_context(item.project_id))
    with connect() as db:
        db.execute("INSERT INTO messages(project_id, role, content) VALUES (?, 'user', ?)", (item.project_id, item.message))
        db.execute("INSERT INTO messages(project_id, role, content) VALUES (?, 'assistant', ?)", (item.project_id, answer))
    return {"answer": answer}

@app.get("/projects/{project_id}/messages")
def project_messages(project_id: int):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT role, content, created_at FROM messages WHERE project_id=? ORDER BY id", (project_id,)).fetchall()]

@app.post("/memories")
def add_memory(item: MemoryIn):
    with connect() as db:
        cur = db.execute("INSERT INTO memories(category, content) VALUES (?, ?)", (item.category, item.content))
        return {"id": cur.lastrowid, "category": item.category, "content": item.content}

@app.get("/memories")
def list_memories():
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT * FROM memories ORDER BY id DESC").fetchall()]

@app.delete("/memories/{memory_id}")
def delete_memory(memory_id: int):
    with connect() as db:
        cur = db.execute("DELETE FROM memories WHERE id=?", (memory_id,))
    if cur.rowcount == 0: raise HTTPException(404, "Memory not found")
    return {"deleted": True}

@app.post("/upload/{project_id}")
async def upload_document(project_id: int, file: UploadFile = File(...)):
    allowed = {".txt", ".md", ".pdf", ".docx", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed: raise HTTPException(400, "File type not supported.")
    with connect() as db:
        if not db.execute("SELECT id FROM projects WHERE id=?", (project_id,)).fetchone():
            raise HTTPException(404, "Project not found")
    content = await file.read()
    if len(content) > 10 * 1024 * 1024: raise HTTPException(413, "File is larger than 10 MB.")
    stored = UPLOAD_DIR / f"{uuid.uuid4().hex}{suffix}"
    stored.write_bytes(content)
    try: extracted = extract_text(stored)
    except Exception as exc:
        stored.unlink(missing_ok=True)
        raise HTTPException(400, f"Could not read file: {exc}")
    with connect() as db:
        cur = db.execute("INSERT INTO documents(project_id, filename, stored_path, extracted_text) VALUES (?, ?, ?, ?)", (project_id, file.filename, str(stored), extracted[:50000]))
    return {"id": cur.lastrowid, "filename": file.filename, "characters_extracted": len(extracted)}

@app.get("/projects/{project_id}/documents")
def project_documents(project_id: int):
    with connect() as db:
        return [dict(r) for r in db.execute("SELECT id, filename, created_at, length(extracted_text) AS characters FROM documents WHERE project_id=? ORDER BY id DESC", (project_id,)).fetchall()]

@app.post("/analyze/code")
def analyze_code(item: CodeIn):
    findings = detect_code_patterns(item.code, item.language)
    with connect() as db:
        for pattern, _ in findings:
            db.execute("""INSERT INTO mistake_patterns(language, pattern, occurrences) VALUES (?, ?, 1)
            ON CONFLICT(language, pattern) DO UPDATE SET occurrences=occurrences+1, last_seen=CURRENT_TIMESTAMP""", (item.language.lower(), pattern))
        rows = db.execute("SELECT pattern, occurrences FROM mistake_patterns WHERE language=? ORDER BY occurrences DESC", (item.language.lower(),)).fetchall()
    prompt = ("Analyze this code. Explain what it does, identify bugs and improvements, and teach the likely cause simply. Do not rewrite everything unless necessary.\n\n" + f"Language: {item.language}\nCode:\n{item.code}\n\nStarter pattern checks: {findings}")
    answer = ai_response(prompt, "Recorded recurring patterns: " + str([dict(r) for r in rows]))
    return {"analysis": answer, "detected_patterns": findings, "pattern_history": [dict(r) for r in rows], "note": "Starter rule-based checks only; not a complete code checker."}

@app.post("/analyze/writing")
def analyze_writing(item: StyleIn):
    prompt = ("Analyze this writing sample's sentence length, tone, vocabulary, paragraph structure, and repeated habits. Give 3 practical observations. Do not infer personal experiences.\n\n" + item.sample)
    return {"analysis": ai_response(prompt)}
