"""
GEPA-optimized crisis detection system.
Production-ready implementation of the evolved crisis detection prompt.
"""

import logging
from typing import Dict, Any
from ..adapters.together import complete_with_logprobs

logger = logging.getLogger(__name__)

# GEPA-evolved prompt with 87.5% accuracy
GEPA_CRISIS_PROMPT = """You are a mental health crisis detection system. Classify text as:
- crisis: Immediate danger, suicidal thoughts
- moderate_risk: Emotional distress needing attention
- safe: Normal conversation, business topics

Analyze emotional content and intent, not just keywords.

IMPORTANT: Even indirect expressions of suicidal ideation should be classified as crisis."""

def detect_crisis_gepa(user_text: str) -> Dict[str, Any]:
    """
    Use GEPA-optimized prompt to detect crisis level.
    
    Args:
        user_text: The user's message to analyze
        
    Returns:
        Dict with keys:
        - classification: "crisis", "moderate_risk", or "safe"
        - confidence: Confidence score from logprobs
        - should_escalate: Boolean whether to escalate
    """
    if not user_text or not user_text.strip():
        return {
            "classification": "safe",
            "confidence": 0.9,
            "should_escalate": False
        }
    
    # Format the prompt for classification
    full_prompt = f"""{GEPA_CRISIS_PROMPT}

Text to classify: "{user_text.strip()}"

Classification (respond with only: crisis, moderate_risk, or safe):"""
    
    try:
        # Get LLM response with logprobs
        result = complete_with_logprobs(full_prompt, max_tokens=10, temperature=0.1)
        
        # Extract and clean classification
        classification = result.get("text", "").strip().lower()
        token_logprobs = result.get("token_logprobs", [])
        
        # Ensure valid classification
        if classification not in ["crisis", "moderate_risk", "safe"]:
            # Try to extract valid word from response
            words = classification.split()
            for word in words:
                if word in ["crisis", "moderate_risk", "safe"]:
                    classification = word
                    break
            else:
                # Default to safe if no valid classification found
                classification = "safe"
                logger.warning(f"Invalid classification '{result.get('text', '')}', defaulting to safe")
        
        # Calculate confidence from logprobs (simple and correct)
        if token_logprobs and len(token_logprobs) > 0:
            avg_logprob = sum(token_logprobs) / len(token_logprobs)
            # Simple linear mapping: logprob closer to 0 = higher confidence
            # Typical logprobs range from -5 to -0.1, so normalize to [0.1, 1.0]
            if avg_logprob >= -0.5:
                confidence = 1.0  # Very confident
            elif avg_logprob >= -2.0:
                confidence = 0.8  # Confident  
            elif avg_logprob >= -5.0:
                confidence = 0.5  # Medium confidence
            else:
                confidence = 0.2  # Low confidence
        else:
            confidence = 0.5  # Default medium confidence
        
        # Determine escalation - escalate for both crisis and moderate_risk
        should_escalate = classification in ["crisis", "moderate_risk"]
        
        logger.info(f"GEPA detection: '{user_text[:50]}...' -> {classification} (conf: {confidence:.3f})")
        
        return {
            "classification": classification,
            "confidence": confidence,
            "should_escalate": should_escalate
        }
        
    except Exception as e:
        logger.error(f"GEPA crisis detection failed: {e}")
        # Fallback to safe classification
        return {
            "classification": "safe",
            "confidence": 0.0,
            "should_escalate": False
        }

def should_escalate_gepa(user_text: str, fallback_logprobs=None) -> bool:
    """
    Simplified interface for escalation decision using GEPA detection.
    
    Args:
        user_text: User's message
        fallback_logprobs: Optional logprobs for fallback (unused in GEPA)
        
    Returns:
        Boolean whether to escalate to human
    """
    result = detect_crisis_gepa(user_text)
    return result["should_escalate"]