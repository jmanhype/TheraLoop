"""
Review queue and escalation endpoints for TheraLoop.
"""
from __future__ import annotations
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from fastapi import Depends, HTTPException
import uuid

# Import auth dependencies  
from ..auth.jwt_auth import require_auth, TokenData

# Storage (swap with DB later)
REVIEW_QUEUE: dict[str, dict] = {}

class EscalationIn(BaseModel):
    conversation_id: str
    user_text: str
    assistant_text: Optional[str] = None
    token_logprob_sum: Optional[float] = None
    policy_tag: Optional[str] = None

class ReviewDecision(BaseModel):
    id: str
    action: str  # "approve" | "defer" | "reject"
    note: Optional[str] = None

def setup_review_endpoints(app):
    """Add review queue endpoints to the app"""
    
    # POST /v1/escalate (called by UI when escalate button is pressed)
    @app.post("/v1/escalate")
    def escalate(payload: EscalationIn):
        """Allow anonymous escalations for better user experience"""
        item_id = str(uuid.uuid4())
        REVIEW_QUEUE[item_id] = {
            "id": item_id,
            "created_at": datetime.utcnow().isoformat() + "Z",
            "conversation_id": payload.conversation_id,
            "user_id": "anonymous",  # Allow anonymous escalations
            "preview": payload.user_text[:400] if payload.user_text else "",
            "assistant_text": payload.assistant_text or "",
            "token_logprob_sum": payload.token_logprob_sum,
            "policy_tag": payload.policy_tag,
            "status": "pending",
        }
        return {"ok": True, "id": item_id}

    # GET /v1/review/queue (clinician)
    @app.get("/v1/review/queue")
    def review_queue(user: TokenData = Depends(require_auth("clinician"))):
        items = [v for v in REVIEW_QUEUE.values() if v["status"] == "pending"]
        # return newest first
        items.sort(key=lambda x: x["created_at"], reverse=True)
        return {"items": items}

    # POST /v1/review/decide (clinician)
    @app.post("/v1/review/decide")
    def review_decide(decision: ReviewDecision, user: TokenData = Depends(require_auth("clinician"))):
        it = REVIEW_QUEUE.get(decision.id)
        if not it:
            raise HTTPException(404, "not found")
        it["status"] = decision.action
        it["decided_by"] = user.user_id
        it["decided_at"] = datetime.utcnow().isoformat() + "Z"
        it["note"] = decision.note or ""
        return {"ok": True, "item": it}