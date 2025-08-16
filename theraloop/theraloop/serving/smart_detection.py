"""
Smart crisis detection using embeddings and multiple signals.
Addresses limitations of keyword-based detection.
"""
import logging
from typing import List, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

class SmartCrisisDetector:
    def __init__(self):
        """Initialize the smart crisis detector with embedding model."""
        try:
            # Use a lightweight, fast model for embeddings
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Smart crisis detector initialized successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self.model = None
        
        # Known crisis patterns for similarity matching
        self.crisis_patterns = [
            "I want to kill myself",
            "I want to die", 
            "I don't want to live anymore",
            "I want to end my life",
            "I can't go on anymore",
            "I don't want to be here anymore",
            "Life isn't worth living",
            "I want to end it all",
            "I wish I was dead",
            "I want to hurt myself",
            "I'm going to kill myself",
            "Nobody would miss me if I was gone",
            "I'd be better off dead",
            "I can't take this anymore"
        ]
        
        # Pre-compute embeddings for crisis patterns
        if self.model:
            try:
                self.pattern_embeddings = self.model.encode(self.crisis_patterns)
                logger.info(f"Pre-computed embeddings for {len(self.crisis_patterns)} crisis patterns")
            except Exception as e:
                logger.error(f"Failed to pre-compute pattern embeddings: {e}")
                self.pattern_embeddings = None
    
    def detect_crisis_by_similarity(self, user_text: str, threshold: float = 0.65) -> Dict[str, Any]:
        """
        Detect crisis using semantic similarity to known patterns.
        
        Args:
            user_text: User's input text
            threshold: Similarity threshold for crisis detection
            
        Returns:
            Dict with detection results
        """
        if not self.model or self.pattern_embeddings is None:
            return {"is_crisis": False, "method": "similarity", "error": "Model not available"}
        
        try:
            # Get embedding for user text
            user_embedding = self.model.encode([user_text])
            
            # Calculate similarities to crisis patterns
            similarities = np.dot(user_embedding, self.pattern_embeddings.T)[0]
            max_similarity = float(np.max(similarities))
            best_match_idx = int(np.argmax(similarities))
            best_match = self.crisis_patterns[best_match_idx]
            
            is_crisis = max_similarity > threshold
            
            return {
                "is_crisis": is_crisis,
                "method": "similarity", 
                "confidence": max_similarity,
                "threshold": threshold,
                "best_match": best_match,
                "all_similarities": similarities.tolist()
            }
            
        except Exception as e:
            logger.error(f"Error in similarity detection: {e}")
            return {"is_crisis": False, "method": "similarity", "error": str(e)}
    
    def detect_crisis_by_response_analysis(self, ai_response: str) -> Dict[str, Any]:
        """
        Detect crisis by analyzing the AI's response content.
        
        Args:
            ai_response: The AI's response text
            
        Returns:
            Dict with detection results
        """
        crisis_indicators = [
            "suicide prevention",
            "crisis hotline", 
            "emergency services",
            "national suicide",
            "harm yourself",
            "feeling suicidal",
            "thoughts of death",
            "crisis text line",
            "mental health crisis",
            "immediate help"
        ]
        
        response_lower = ai_response.lower()
        found_indicators = [ind for ind in crisis_indicators if ind in response_lower]
        
        # If AI mentioned multiple crisis resources, likely a crisis
        is_crisis = len(found_indicators) >= 2
        
        return {
            "is_crisis": is_crisis,
            "method": "response_analysis",
            "indicators_found": found_indicators,
            "indicator_count": len(found_indicators)
        }
    
    def detect_crisis_multi_signal(
        self, 
        user_text: str, 
        ai_response: str, 
        token_logprobs: List[float] = None,
        confidence_threshold: float = -30.0
    ) -> Dict[str, Any]:
        """
        Multi-signal crisis detection combining multiple methods.
        
        Args:
            user_text: User's input
            ai_response: AI's response  
            token_logprobs: Token log probabilities
            confidence_threshold: Confidence threshold for low confidence signal
            
        Returns:
            Dict with comprehensive detection results
        """
        signals = []
        detection_results = {}
        
        # Signal 1: Semantic similarity
        similarity_result = self.detect_crisis_by_similarity(user_text)
        detection_results["similarity"] = similarity_result
        if similarity_result.get("is_crisis", False):
            signals.append("high_similarity")
        
        # Signal 2: Response analysis
        response_result = self.detect_crisis_by_response_analysis(ai_response)
        detection_results["response_analysis"] = response_result
        if response_result.get("is_crisis", False):
            signals.append("crisis_response")
        
        # Signal 3: Low confidence (existing logic)
        if token_logprobs:
            confidence_score = sum(token_logprobs)
            detection_results["confidence"] = {
                "score": confidence_score,
                "threshold": confidence_threshold,
                "is_low_confidence": confidence_score < confidence_threshold
            }
            if confidence_score < confidence_threshold:
                signals.append("low_confidence")
        
        # Decision logic: escalate if multiple signals or high-confidence crisis signal
        should_escalate = (
            len(signals) >= 2 or 
            "high_similarity" in signals or
            ("crisis_response" in signals and similarity_result.get("confidence", 0) > 0.4)
        )
        
        return {
            "should_escalate": should_escalate,
            "signals": signals,
            "signal_count": len(signals),
            "method": "multi_signal",
            "details": detection_results
        }

# Global detector instance
_detector = None

def get_detector() -> SmartCrisisDetector:
    """Get global crisis detector instance."""
    global _detector
    if _detector is None:
        _detector = SmartCrisisDetector()
    return _detector

def should_escalate_smart(user_text: str, ai_response: str, token_logprobs: List[float] = None) -> bool:
    """
    Smart escalation decision using multiple detection methods.
    
    Args:
        user_text: User's input text
        ai_response: AI's response
        token_logprobs: Token log probabilities
        
    Returns:
        Boolean indicating whether to escalate
    """
    detector = get_detector()
    result = detector.detect_crisis_multi_signal(user_text, ai_response, token_logprobs)
    
    # Log detection details for monitoring
    logger.info(f"Smart detection: {result['should_escalate']}, signals: {result['signals']}")
    
    return result["should_escalate"]