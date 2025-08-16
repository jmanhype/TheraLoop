import os
from ..metrics.util import safe_sum
from .gepa_detection import should_escalate_gepa
import logging

logger = logging.getLogger(__name__)

THRESH = float(os.getenv("THERALOOP_CONFIDENCE_THRESHOLD","-30.0"))  # More sensitive threshold

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "end my life", "self-harm", "hurt myself",
    "panic attack", "crisis", "emergency", "can't breathe",
    "overdose", "cutting", "harming myself", "want to die",
    "don't want to live", "life isn't worth"
]

def should_escalate(token_logprobs, text=""):
    """Determine if conversation should be escalated to human.
    
    Escalates if:
    1. Confidence is very low (sum of logprobs < threshold)
    2. Crisis keywords are detected in the text
    """
    # Check confidence threshold
    if safe_sum(token_logprobs) < THRESH:
        return True
    
    # Check for crisis keywords
    if text:
        text_lower = text.lower()
        for keyword in CRISIS_KEYWORDS:
            if keyword in text_lower:
                return True
    
    return False

def should_escalate_enhanced(token_logprobs, text=""):
    """Enhanced escalation with GEPA detection option.
    
    Uses environment variable to choose detection method:
    - THERALOOP_USE_GEPA=true: Use GEPA-optimized detection
    - THERALOOP_USE_GEPA=false: Use legacy keyword detection (default)
    """
    # Validate environment variable value
    gepa_env = os.getenv("THERALOOP_USE_GEPA", "false").lower().strip()
    use_gepa = gepa_env in ["true", "1", "yes", "on"]
    
    if use_gepa and text:
        try:
            # Use GEPA detection if enabled
            gepa_result = should_escalate_gepa(text)
            logger.info(f"GEPA detection used: {gepa_result}")
            return gepa_result
        except Exception as e:
            logger.error(f"GEPA detection failed, falling back to keywords: {e}")
            # Fall back to keyword detection on error
    
    # Default: use legacy keyword + confidence detection
    return should_escalate(token_logprobs, text)
