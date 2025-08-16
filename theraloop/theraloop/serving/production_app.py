# theraloop/serving/production_app.py
from __future__ import annotations
import os, json, hashlib, time
from fastapi import FastAPI, Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
from ..adapters.together import complete_with_logprobs
from .router import should_escalate

SAFE_MODE = os.getenv("SAFE_MODE", "0") == "1"
PROMPT_PATH = os.getenv("THERALOOP_PROMPT_PATH", "outputs/best_prompt.txt")
PROMPT = open(PROMPT_PATH).read() if os.path.exists(PROMPT_PATH) else "Be concise."
VERSION = os.getenv("THERALOOP_VERSION", "v0.1")

app = FastAPI(title="TheraLoop API", version=VERSION)

class Query(BaseModel):
    question: str
    metadata: Optional[Dict[str, Any]] = None

class Response(BaseModel):
    text: str
    token_logprob_sum: float
    escalate: bool
    safe: bool

@app.get("/healthz")
def healthz():
    return {"ok": True, "version": VERSION, "safe_mode": SAFE_MODE}

@app.get("/version")
def version():
    return {"version": VERSION}

@app.post("/v1/score", response_model=Response)
def score(req: Query):
    rendered = f"{PROMPT}\n\nTask:\n{req.question}\nReturn only the answer."
    out = complete_with_logprobs(rendered, max_tokens=256)
    escalation = should_escalate(out.get("token_logprobs", []))
    
    # Simple safety check (placeholder)
    safe = not any(word in out.get("text", "").lower() for word in ["unsafe", "danger", "error"])
    
    # Optional redaction
    text = out.get("text", "")
    if SAFE_MODE and not safe:
        text = "[REDACTED]"
    
    return Response(
        text=text.strip(),
        token_logprob_sum=float(sum(out.get("token_logprobs", []) or [])),
        escalate=bool(escalation) or (not safe),
        safe=bool(safe)
    )

@app.post("/v1/answer", response_model=Response)
def answer(req: Query):
    # Identical to /v1/score; kept for semantic clarity
    return score(req)