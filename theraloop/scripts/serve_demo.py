import os
import uuid
import logging
import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from theraloop.adapters.together import complete_with_logprobs
from theraloop.serving.router import should_escalate_enhanced
from theraloop.persistence.database import get_db

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load prompt with proper error handling
try:
    with open("outputs/best_prompt.txt", "r") as f:
        PROMPT = f.read()
except (FileNotFoundError, IOError, PermissionError):
    PROMPT = "Be concise."

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Query(BaseModel):
    question: str
    conversation_id: Optional[str] = None  # Allow tracking conversations

class EscalationRequest(BaseModel):
    conversation_id: str
    user_text: str
    assistant_text: Optional[str] = None
    token_logprob_sum: Optional[float] = None
    policy_tag: Optional[str] = None

@app.post("/answer")
def answer(q: Query):
    db = get_db()
    
    try:
        # Validate or create conversation
        conversation_id = q.conversation_id
        if conversation_id:
            # Validate that conversation exists
            if not db.conversation_exists(conversation_id):
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            # Create new conversation
            conversation_id = db.create_conversation({"source": "api"})
        
        # Store user message
        db.add_message(conversation_id, "user", q.question)
        
        # Get conversation history for context with proper limits
        history = db.get_conversation_history(conversation_id)
        
        # Build conversation context with strict token management
        context_messages = []
        total_context_chars = 0
        MAX_CONTEXT_CHARS = 1500  # Conservative limit for context
        MAX_MESSAGE_CHARS = 200   # Truncate very long individual messages
        
        # Process messages in reverse (newest first) to prioritize recent context
        for msg in reversed(history[-8:]):  # Last 8 messages maximum
            role = msg['role']
            content = msg['content'] or ""
            
            # Truncate individual messages if too long
            if len(content) > MAX_MESSAGE_CHARS:
                content = content[:MAX_MESSAGE_CHARS] + "..."
            
            message_text = f"{role.title()}: {content}"
            
            # Check if adding this message would exceed context limit
            if total_context_chars + len(message_text) > MAX_CONTEXT_CHARS:
                break
                
            context_messages.insert(0, message_text)  # Insert at beginning to maintain order
            total_context_chars += len(message_text)
        
        # Build consistent prompt structure
        if context_messages:
            conversation_context = "\n".join(context_messages)
            prompt_with_context = f"{PROMPT}\n\nConversation History:\n{conversation_context}\n\nUser: {q.question}\n\nRespond naturally, maintaining conversation continuity:"
        else:
            prompt_with_context = f"{PROMPT}\n\nUser: {q.question}\n\nRespond naturally:"
            
        out = complete_with_logprobs(prompt_with_context, max_tokens=128)
        logprobs = out.get("token_logprobs", [])
        escalate = should_escalate_enhanced(logprobs, text=q.question)  # Use enhanced detection with GEPA option
        confidence_sum = sum(logprobs or [])
        answer_text = (out.get("text","") or "").strip()
        
        # Store assistant response
        db.add_message(
            conversation_id, 
            "assistant", 
            answer_text,
            confidence_score=confidence_sum,
            token_logprobs=logprobs
        )
        
        return {
            "answer": answer_text,
            "confidence_logprob_sum": confidence_sum,
            "escalate": bool(escalate),
            "conversation_id": conversation_id
        }
    except HTTPException:
        # Re-raise HTTP exceptions (like 404)
        raise
    except sqlite3.Error as e:
        # Database-specific errors
        logger.error(f"Database error in answer endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        # Other errors (API, network, etc.)
        logger.error(f"Error in answer endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.post("/escalate")
def escalate_to_human(payload: EscalationRequest):
    """Handle escalation requests when confidence is low or crisis detected"""
    db = get_db()
    
    try:
        # Validate conversation exists
        if not db.conversation_exists(payload.conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Store escalation in database
        escalation_id = db.create_escalation(
            conversation_id=payload.conversation_id,
            user_text=payload.user_text,
            assistant_text=payload.assistant_text,
            confidence_score=payload.token_logprob_sum,
            policy_tag=payload.policy_tag
        )
        
        # Log escalation for audit trail
        user_text_preview = payload.user_text[:50] + ("..." if len(payload.user_text) > 50 else "")
        logger.info(
            f"Escalation {escalation_id}: "
            f"conversation={payload.conversation_id}, "
            f"user_text='{user_text_preview}', "
            f"confidence={payload.token_logprob_sum}, "
            f"policy={payload.policy_tag}"
        )
        
        return {
            "ok": True,
            "id": escalation_id
        }
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error(f"Database error in escalate endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in escalate endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.get("/stats")
def get_stats():
    """Get system statistics"""
    db = get_db()
    
    try:
        return db.get_conversation_stats()
    except sqlite3.Error as e:
        logger.error(f"Database error in stats endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in stats endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.get("/conversation/{conversation_id}/history")
def get_conversation_history(conversation_id: str):
    """Get conversation history"""
    db = get_db()
    
    try:
        # Validate conversation exists
        if not db.conversation_exists(conversation_id):
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        messages = db.get_conversation_history(conversation_id)
        return {"messages": messages}
    except HTTPException:
        raise
    except sqlite3.Error as e:
        logger.error(f"Database error in history endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in history endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")

@app.get("/escalations/pending")
def get_pending_escalations():
    """Get all pending escalations for human review"""
    db = get_db()
    
    try:
        return {"escalations": db.get_pending_escalations()}
    except sqlite3.Error as e:
        logger.error(f"Database error in pending escalations endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail="Database temporarily unavailable")
    except Exception as e:
        logger.error(f"Error in pending escalations endpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Service temporarily unavailable")
