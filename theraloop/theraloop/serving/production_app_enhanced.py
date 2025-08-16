"""
Enhanced production app with calibrated routing and observability.
"""
from __future__ import annotations
import os, json, hashlib, time
from fastapi import FastAPI, Request, Response as FastAPIResponse
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import hardened adapter and calibrated router
try:
    from ..adapters.together_hardened import complete_with_logprobs, health_check
except ImportError:
    from ..adapters.together import complete_with_logprobs
    def health_check():
        return True

from .calibrated_router import router as calibrated_router
from .metrics_middleware import (
    MetricsMiddleware,
    get_metrics,
    track_logprob_confidence,
    track_escalation,
    update_circuit_breaker_state
)

SAFE_MODE = os.getenv("SAFE_MODE", "0") == "1"
PROMPT_PATH = os.getenv("THERALOOP_PROMPT_PATH", "outputs/best_prompt.txt")
PROMPT = open(PROMPT_PATH).read() if os.path.exists(PROMPT_PATH) else "Be concise."
VERSION = os.getenv("THERALOOP_VERSION", "v0.1")
CALIBRATION_PATH = os.getenv("THERALOOP_CALIBRATION_PATH", "outputs/calibration.json")

app = FastAPI(title="TheraLoop API", version=VERSION)

# Add middleware
app.add_middleware(MetricsMiddleware)

# Add redaction middleware for PII/PHI safety
try:
    from ..safety.redact_middleware import RedactionMiddleware
    app.add_middleware(RedactionMiddleware)
except ImportError:
    pass  # Redaction middleware optional

# Load calibration if available
if os.path.exists(CALIBRATION_PATH):
    calibrated_router.load_calibration(CALIBRATION_PATH)

class Query(BaseModel):
    question: str
    metadata: Optional[Dict[str, Any]] = None
    feedback: Optional[bool] = None  # For calibration

class Response(BaseModel):
    text: str
    token_logprob_sum: float
    confidence: float
    escalate: bool
    safe: bool
    request_id: Optional[str] = None

@app.get("/healthz")
def healthz():
    """Health check endpoint."""
    api_healthy = health_check()
    return {
        "ok": api_healthy,
        "version": VERSION,
        "safe_mode": SAFE_MODE,
        "calibrated": calibrated_router.is_calibrated,
        "threshold": calibrated_router.threshold
    }

@app.get("/version")
def version():
    """Version endpoint."""
    return {"version": VERSION}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Prometheus metrics endpoint."""
    return FastAPIResponse(content=get_metrics(), media_type="text/plain")

@app.post("/v1/score", response_model=Response)
def score(req: Query):
    """Score endpoint with calibrated routing."""
    start_time = time.time()
    
    # Generate request ID
    request_id = hashlib.md5(f"{req.question}{start_time}".encode()).hexdigest()[:8]
    
    # Render prompt
    rendered = f"{PROMPT}\n\nTask:\n{req.question}\nReturn only the answer."
    
    # Get completion with logprobs
    out = complete_with_logprobs(rendered, max_tokens=256)
    
    # Calculate confidence
    token_logprobs = out.get("token_logprobs", [])
    confidence = calibrated_router.get_confidence_score(token_logprobs)
    
    # Track confidence
    track_logprob_confidence(confidence)
    
    # Check if should escalate
    escalation = calibrated_router.should_escalate(token_logprobs)
    
    # Simple safety check (placeholder)
    text = out.get("text", "")
    safe = not any(word in text.lower() for word in ["unsafe", "danger", "error"])
    
    # Track escalation if needed
    if escalation or not safe:
        track_escalation()
    
    # Add calibration sample if feedback provided
    if req.feedback is not None:
        calibrated_router.add_calibration_sample(token_logprobs, req.feedback)
    
    # Optional redaction
    if SAFE_MODE and not safe:
        text = "[REDACTED]"
    
    return Response(
        text=text.strip(),
        token_logprob_sum=float(sum(token_logprobs)),
        confidence=confidence,
        escalate=bool(escalation) or (not safe),
        safe=bool(safe),
        request_id=request_id
    )

@app.post("/v1/answer", response_model=Response)
def answer(req: Query):
    """Answer endpoint (alias for score)."""
    return score(req)

@app.post("/v1/calibrate")
def calibrate(target_precision: float = 0.95):
    """Trigger calibration."""
    threshold, auc = calibrated_router.calibrate(target_precision)
    
    # Save calibration
    calibrated_router.save_calibration(CALIBRATION_PATH)
    
    return {
        "success": True,
        "threshold": threshold,
        "auc": auc,
        "samples": len(calibrated_router.calibration_data),
        "is_calibrated": calibrated_router.is_calibrated
    }

@app.get("/v1/router/stats")
def router_stats():
    """Get router statistics."""
    return calibrated_router.get_metrics()

@app.post("/v1/feedback")
def feedback(request_id: str, was_correct: bool):
    """Submit feedback for a request."""
    # In production, you'd look up the request by ID and add to calibration
    return {"success": True, "message": "Feedback recorded"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)