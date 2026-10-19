import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("FRIDEY_DB_PATH", str(ROOT / "fridey.db")))
INDEX_PATH = ROOT / "index.html"
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

app = FastAPI(title="Fridey", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def connect_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                prompt TEXT NOT NULL,
                status TEXT NOT NULL,
                result TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)


init_db()


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    history: list[dict] = Field(default_factory=list, max_length=30)


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    prompt: str = Field(min_length=1, max_length=12000)


@app.get("/")
def home():
    if not INDEX_PATH.exists():
        raise HTTPException(status_code=404, detail="Frontend file not found")
    return FileResponse(INDEX_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "app": "fridey"}


@app.get("/api/tasks")
def list_tasks():
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tasks ORDER BY created_at DESC LIMIT 100"
        ).fetchall()
    return {"tasks": [dict(row) for row in rows]}


@app.post("/api/tasks")
def create_task(body: TaskCreate):
    task_id = str(uuid.uuid4())
    stamp = now_iso()
    with connect_db() as conn:
        conn.execute(
            "INSERT INTO tasks (id,title,prompt,status,result,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (task_id, body.title.strip(), body.prompt.strip(), "queued", None, stamp, stamp),
        )
    return {"task": {"id": task_id, "title": body.title.strip(), "prompt": body.prompt.strip(),
                     "status": "queued", "result": None, "created_at": stamp, "updated_at": stamp}}


@app.get("/api/tasks/{task_id}")
def get_task(task_id: str):
    with connect_db() as conn:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": dict(row)}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: str):
    with connect_db() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"deleted": True, "id": task_id}


@app.post("/api/chat")
def chat(body: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Set OPENAI_API_KEY in your Render environment.")
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, timeout=45.0, max_retries=1)
        messages = [{"role": "system", "content": (
            "You are Fridey, a helpful general-purpose AI assistant. Be clear and practical. "
            "Do not claim to have performed external actions unless a connected tool actually did so."
        )}]
        for item in body.history[-20:]:
            role = item.get("role")
            content = item.get("content")
            if role in ("user", "assistant") and isinstance(content, str):
                messages.append({"role": role, "content": content[:12000]})
        messages.append({"role": "user", "content": body.message})
        response = client.chat.completions.create(model=MODEL, messages=messages)
        answer = response.choices[0].message.content or ""
        return {"reply": answer, "model": MODEL}
    except HTTPException:
        raise
    except Exception as exc:
        # Avoid returning provider error details or secrets to the client.
        raise HTTPException(status_code=502, detail="The AI provider request failed. Check server logs and API configuration.") from exc
