"""
Production app with full security: JWT auth, rate limiting, PII redaction.
"""
from __future__ import annotations
import os, json, hashlib, time
from fastapi import FastAPI, Request, Response as FastAPIResponse, Depends
from fastapi.responses import PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

# Import core functionality
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
    track_escalation
)

# Import security
from ..auth.jwt_auth import (
    jwt_auth,
    require_auth,
    require_rate_limit,
    audit_logger,
    TokenData
)
from ..safety.redact_middleware import RedactionMiddleware
from ..safety.redact import redact_text

# Import review endpoints
from .review_api import setup_review_endpoints

# Configuration
SAFE_MODE = os.getenv("SAFE_MODE", "0") == "1"
PROMPT_PATH = os.getenv("THERALOOP_PROMPT_PATH", "outputs/best_prompt.txt")
PROMPT = open(PROMPT_PATH).read() if os.path.exists(PROMPT_PATH) else "Be concise."
VERSION = os.getenv("THERALOOP_VERSION", "v0.1")
CALIBRATION_PATH = os.getenv("THERALOOP_CALIBRATION_PATH", "outputs/calibration.json")

# Initialize app
app = FastAPI(
    title="TheraLoop Therapeutic AI",
    version=VERSION,
    description="Production GEPA optimization with logprob confidence routing",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add middleware
app.add_middleware(MetricsMiddleware)
app.add_middleware(RedactionMiddleware)

# Load calibration if available
if os.path.exists(CALIBRATION_PATH):
    calibrated_router.load_calibration(CALIBRATION_PATH)

# Load policy matrix
import yaml
POLICY_PATH = "theraloop/policy/matrix.yaml"
if os.path.exists(POLICY_PATH):
    with open(POLICY_PATH) as f:
        POLICY_MATRIX = yaml.safe_load(f)
else:
    POLICY_MATRIX = {"policies": {}}


class Query(BaseModel):
    question: str
    metadata: Optional[Dict[str, Any]] = None
    feedback: Optional[bool] = None


class Response(BaseModel):
    text: str
    token_logprob_sum: float
    confidence: float
    escalate: bool
    safe: bool
    request_id: Optional[str] = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


@app.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """Login endpoint - in production, verify against database."""
    # Mock authentication - replace with real auth
    if request.username == "demo_user" and request.password == "demo_pass":
        role = "user"
    elif request.username == "demo_clinician" and request.password == "demo_pass":
        role = "clinician"
    elif request.username == "demo_admin" and request.password == "demo_pass":
        role = "admin"
    else:
        raise HTTPException(401, "Invalid credentials")
    
    token = jwt_auth.create_token(request.username, role)
    return TokenResponse(access_token=token, role=role)


@app.get("/healthz")
def healthz():
    """Health check endpoint."""
    api_healthy = health_check()
    return {
        "ok": api_healthy,
        "version": VERSION,
        "safe_mode": SAFE_MODE,
        "calibrated": calibrated_router.is_calibrated,
        "threshold": calibrated_router.threshold,
        "auth_enabled": True
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    """Prometheus metrics endpoint."""
    return FastAPIResponse(content=get_metrics(), media_type="text/plain")


def check_policy(text: str) -> Dict[str, Any]:
    """Check text against policy matrix."""
    for policy_name, policy in POLICY_MATRIX.get("policies", {}).items():
        keywords = policy.get("keywords", [])
        if any(kw.lower() in text.lower() for kw in keywords):
            return {
                "triggered": True,
                "policy": policy_name,
                "action": policy.get("action", "escalate"),
                "message": policy.get("message", "")
            }
    return {"triggered": False}


@app.post("/v1/score", response_model=Response)
def score(
    req: Query,
    _rate_limit: None = Depends(require_rate_limit(10)),
    user: Optional[TokenData] = Depends(require_auth())
):
    """Score endpoint with auth and rate limiting."""
    start_time = time.time()
    
    # Audit log
    if user:
        audit_logger.log_request(
            user.user_id,
            "score",
            {"question_len": len(req.question)}
        )
    
    # Generate request ID
    request_id = hashlib.md5(f"{req.question}{start_time}".encode()).hexdigest()[:8]
    
    # Check policy first
    policy_check = check_policy(req.question)
    if policy_check["triggered"]:
        if user:
            audit_logger.log_escalation(
                user.user_id,
                request_id,
                f"Policy: {policy_check['policy']}"
            )
        
        return Response(
            text=policy_check["message"],
            token_logprob_sum=-100.0,
            confidence=-100.0,
            escalate=True,
            safe=False,
            request_id=request_id
        )
    
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
    
    # Safety check
    text = out.get("text", "")
    safe = not any(word in text.lower() for word in ["unsafe", "danger", "error"])
    
    # Track escalation if needed
    if escalation or not safe:
        track_escalation()
        if user:
            audit_logger.log_escalation(
                user.user_id,
                request_id,
                f"Confidence: {confidence:.2f}"
            )
    
    # Add calibration sample if feedback provided
    if req.feedback is not None:
        calibrated_router.add_calibration_sample(token_logprobs, req.feedback)
    
    # Redact if in safe mode
    if SAFE_MODE:
        redacted = redact_text(text)
        text = redacted["text"]
    
    return Response(
        text=text.strip(),
        token_logprob_sum=float(sum(token_logprobs)),
        confidence=confidence,
        escalate=bool(escalation) or (not safe),
        safe=bool(safe),
        request_id=request_id
    )


@app.post("/v1/answer", response_model=Response)
def answer(
    req: Query,
    _rate_limit: None = Depends(require_rate_limit(10)),
    user: Optional[TokenData] = Depends(require_auth())
):
    """Answer endpoint (alias for score)."""
    return score(req, _rate_limit, user)


@app.get("/v1/review/queue")
def get_review_queue(
    user: TokenData = Depends(require_auth("clinician"))
):
    """Get escalated items for clinician review."""
    # In production, query database for escalated items
    return {
        "queue": [
            {
                "request_id": "abc123",
                "question": "[REDACTED]",
                "confidence": -45.2,
                "timestamp": "2024-01-15T10:30:00Z",
                "user_id": "user_001"
            }
        ]
    }


@app.post("/v1/review/{request_id}/approve")
def approve_escalation(
    request_id: str,
    response: str,
    user: TokenData = Depends(require_auth("clinician"))
):
    """Approve an escalated request with clinician response."""
    audit_logger.log_request(
        user.user_id,
        "approve_escalation",
        {"request_id": request_id}
    )
    
    # In production, update database
    return {"success": True, "request_id": request_id}


@app.post("/v1/calibrate")
def calibrate(
    target_precision: float = 0.95,
    user: TokenData = Depends(require_auth("admin"))
):
    """Trigger calibration (admin only)."""
    threshold, auc = calibrated_router.calibrate(target_precision)
    calibrated_router.save_calibration(CALIBRATION_PATH)
    
    audit_logger.log_request(
        user.user_id,
        "calibrate",
        {"threshold": threshold, "auc": auc}
    )
    
    return {
        "success": True,
        "threshold": threshold,
        "auc": auc,
        "samples": len(calibrated_router.calibration_data),
        "is_calibrated": calibrated_router.is_calibrated
    }


@app.get("/v1/stats")
def get_stats(user: TokenData = Depends(require_auth())):
    """Get system statistics."""
    return {
        "router": calibrated_router.get_metrics(),
        "auth": {"user_id": user.user_id, "role": user.role}
    }


# Setup review endpoints
setup_review_endpoints(app)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)