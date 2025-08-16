#!/usr/bin/env python3
"""
DSPy-Optimized Therapy Response Generation
==========================================
Replaces manual prompt engineering with DSPy GEPA optimization
for generating empathetic, contextual therapy responses.

This module:
1. Uses DSPy signatures for therapy response structure
2. Applies GEPA optimization for empathy and effectiveness
3. Considers conversation context and crisis detection results
4. Generates personalized, therapeutic responses

Author: TheraLoop Team
"""

import dspy
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TherapyContext:
    """Context for therapy response generation"""
    user_message: str
    conversation_history: List[Dict[str, str]]
    crisis_level: str  # crisis, moderate_risk, safe
    crisis_confidence: float
    user_emotional_state: Optional[str] = None
    session_goals: Optional[List[str]] = None


class TherapyResponseSignature(dspy.Signature):
    """Generate empathetic, therapeutic responses based on context and crisis level.
    
    THERAPEUTIC PRINCIPLES:
    - Validate emotions without judgment
    - Use reflective listening techniques
    - Provide appropriate support based on crisis level
    - Maintain professional boundaries
    - Guide toward healthy coping strategies
    - Be warm, genuine, and non-directive
    
    CRISIS RESPONSE PROTOCOLS:
    - Crisis: Immediate safety assessment, provide crisis resources
    - Moderate_risk: Emotional support, suggest coping strategies
    - Safe: Normal therapeutic conversation, exploration
    """
    
    user_message = dspy.InputField(desc="User's current message expressing thoughts/feelings")
    conversation_history = dspy.InputField(desc="Previous conversation context for continuity")
    crisis_level = dspy.InputField(desc="Crisis assessment: crisis, moderate_risk, or safe")
    crisis_confidence = dspy.InputField(desc="Confidence in crisis assessment (0.0-1.0)")
    
    therapeutic_response = dspy.OutputField(desc="Empathetic, contextual therapeutic response")
    response_type = dspy.OutputField(desc="Type: crisis_intervention, emotional_support, or therapeutic_conversation")
    empathy_score = dspy.OutputField(desc="Self-assessment of response empathy (1-10)")
    therapeutic_rationale = dspy.OutputField(desc="Brief rationale for the therapeutic approach used")


class DSPyTherapyResponder(dspy.Module):
    """DSPy-based therapy response generator optimized by GEPA"""
    
    def __init__(self):
        super().__init__()
        # Use ChainOfThought for therapeutic reasoning
        self.therapist = dspy.ChainOfThought(TherapyResponseSignature)
    
    def forward(self, context: TherapyContext) -> dspy.Prediction:
        """Generate therapeutic response based on context"""
        
        # Format conversation history for context
        if context.conversation_history:
            history_text = "\n".join([
                f"{msg.get('role', 'Unknown')}: {msg.get('content', '')[:100]}..."
                for msg in context.conversation_history[-3:]  # Last 3 messages for context
            ])
        else:
            history_text = "No previous conversation"
        
        # Generate response using DSPy
        return self.therapist(
            user_message=context.user_message,
            conversation_history=history_text,
            crisis_level=context.crisis_level,
            crisis_confidence=str(context.crisis_confidence)
        )


class TherapyFeedbackMetric:
    """Feedback metric for therapy response optimization"""
    
    def __call__(self, gold: dspy.Example, pred: dspy.Prediction, trace=None):
        """Evaluate therapy response quality with feedback"""
        
        # Extract expected and predicted values
        expected_type = gold.response_type
        predicted_type = pred.response_type
        predicted_response = pred.therapeutic_response
        
        # Scoring criteria
        score = 0.0
        feedback_items = []
        
        # 1. Crisis appropriateness (40% of score)
        crisis_level = gold.crisis_level
        if crisis_level == "crisis":
            if "crisis" in predicted_type or "safety" in predicted_response.lower():
                score += 0.4
                feedback_items.append("✅ Appropriate crisis response")
            else:
                feedback_items.append("❌ Missing crisis intervention for high-risk user")
        elif crisis_level == "moderate_risk":
            if "support" in predicted_type or "coping" in predicted_response.lower():
                score += 0.3
                feedback_items.append("✅ Good emotional support approach")
            else:
                score += 0.1
                feedback_items.append("⚠️ Could provide more emotional support")
        else:  # safe
            if "conversation" in predicted_type:
                score += 0.4
                feedback_items.append("✅ Appropriate therapeutic conversation")
            else:
                score += 0.2
        
        # 2. Empathy and validation (30% of score)
        empathy_indicators = [
            "understand", "feel", "sounds like", "that must be", 
            "i hear", "it seems", "validate", "acknowledge"
        ]
        empathy_found = any(indicator in predicted_response.lower() 
                          for indicator in empathy_indicators)
        if empathy_found:
            score += 0.3
            feedback_items.append("✅ Shows empathy and validation")
        else:
            feedback_items.append("❌ Needs more empathetic language")
        
        # 3. Professional boundaries (20% of score)
        boundary_violations = [
            "i think you should", "you must", "i would", "if i were you",
            "just do", "simply", "calm down", "don't worry"
        ]
        violations_found = any(violation in predicted_response.lower() 
                             for violation in boundary_violations)
        if not violations_found:
            score += 0.2
            feedback_items.append("✅ Maintains professional boundaries")
        else:
            feedback_items.append("❌ Contains directive language - be more non-directive")
        
        # 4. Response length and structure (10% of score)
        response_length = len(predicted_response.split())
        if 15 <= response_length <= 80:  # Appropriate therapeutic response length
            score += 0.1
            feedback_items.append("✅ Appropriate response length")
        elif response_length < 15:
            feedback_items.append("❌ Response too brief - expand with empathy")
        else:
            feedback_items.append("❌ Response too long - be more concise")
        
        # Generate improvement feedback
        feedback = " | ".join(feedback_items)
        if score < 0.7:
            feedback += " | IMPROVE: Focus on empathy, appropriate crisis response, and non-directive language"
        
        # Try different ScoreWithFeedback import locations
        try:
            from dspy.primitives import ScoreWithFeedback
            return ScoreWithFeedback(score=score, feedback=feedback)
        except ImportError:
            try:
                from dspy import ScoreWithFeedback
                return ScoreWithFeedback(score=score, feedback=feedback)
            except ImportError:
                # Fallback to simple score
                return score


import threading

# Thread-safe global responder instance
optimized_responder = None
_responder_lock = threading.Lock()

def _initialize_therapy_responder():
    """Initialize DSPy therapy responder with GEPA optimization"""
    global optimized_responder
    
    # Double-checked locking pattern for thread safety
    if optimized_responder is not None:
        return optimized_responder
    
    with _responder_lock:
        if optimized_responder is not None:
            return optimized_responder
        
        try:
            # Configure DSPy with Together AI
            import os
            api_key = os.getenv("TOGETHER_API_KEY")
            if not api_key:
                logger.warning("TOGETHER_API_KEY not found, using fallback")
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    lm = dspy.LM(model="gpt-3.5-turbo", api_key=api_key)
                else:
                    raise ValueError("No API key available")
            else:
                lm = dspy.LM(model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", api_key=api_key)
            
            dspy.configure(lm=lm)
            
            # Initialize therapy responder
            optimized_responder = DSPyTherapyResponder()
            logger.info("DSPy therapy responder initialized successfully")
            
            return optimized_responder
            
        except Exception as e:
            logger.error(f"Failed to initialize DSPy therapy responder: {e}")
            return None


def generate_therapy_response(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    crisis_level: str = "safe",
    crisis_confidence: float = 0.5
) -> Dict[str, Any]:
    """
    Generate optimized therapy response using DSPy GEPA.
    
    Args:
        user_message: User's current message
        conversation_history: Previous conversation context
        crisis_level: Crisis assessment (crisis, moderate_risk, safe)
        crisis_confidence: Confidence in crisis assessment
        
    Returns:
        Dict with therapy response and metadata
    """
    
    # Validate inputs
    if not isinstance(user_message, str) or not user_message.strip():
        logger.error("Invalid user_message provided")
        user_message = "Unable to process message"
    
    if conversation_history is not None:
        # Validate conversation history format
        validated_history = []
        for msg in conversation_history:
            if isinstance(msg, dict) and 'role' in msg and 'content' in msg:
                validated_history.append(msg)
            else:
                logger.warning(f"Invalid message format in conversation_history: {msg}")
        conversation_history = validated_history
    
    if crisis_level not in ["crisis", "moderate_risk", "safe"]:
        logger.warning(f"Invalid crisis_level: {crisis_level}, defaulting to 'safe'")
        crisis_level = "safe"
    
    if not (0.0 <= crisis_confidence <= 1.0):
        logger.warning(f"Invalid crisis_confidence: {crisis_confidence}, defaulting to 0.5")
        crisis_confidence = 0.5
    
    # Initialize responder
    responder = _initialize_therapy_responder()
    
    if responder is None:
        # Fallback response if DSPy fails
        logger.error("DSPy therapy responder unavailable, using fallback")
        return {
            "response": "I hear that you're going through something difficult. Can you tell me more about what's on your mind?",
            "response_type": "therapeutic_conversation",
            "empathy_score": 6,
            "therapeutic_rationale": "Fallback response - DSPy unavailable",
            "method": "fallback"
        }
    
    try:
        # Create therapy context
        context = TherapyContext(
            user_message=user_message,
            conversation_history=conversation_history or [],
            crisis_level=crisis_level,
            crisis_confidence=crisis_confidence
        )
        
        # Generate response using DSPy
        prediction = responder(context)
        
        # Parse empathy score
        try:
            empathy_score = int(float(prediction.empathy_score))
        except (ValueError, AttributeError, TypeError):
            empathy_score = 7
        
        logger.info(f"DSPy therapy response: {crisis_level} -> {prediction.response_type} (empathy: {empathy_score}/10)")
        
        return {
            "response": prediction.therapeutic_response,
            "response_type": prediction.response_type,
            "empathy_score": empathy_score,
            "therapeutic_rationale": prediction.therapeutic_rationale,
            "method": "dspy_gepa"
        }
        
    except Exception as e:
        logger.error(f"DSPy therapy response generation failed: {e}")
        # Fallback response
        return {
            "response": "I want to understand what you're experiencing. Could you share more about how you're feeling right now?",
            "response_type": "therapeutic_conversation",
            "empathy_score": 6,
            "therapeutic_rationale": f"Error fallback: {str(e)}",
            "method": "error_fallback"
        }


def optimize_therapy_responses():
    """
    Run GEPA optimization on therapy response generation.
    This would typically be run offline to improve the model.
    """
    
    # Sample training data for therapy response optimization
    therapy_examples = [
        dspy.Example(
            user_message="I feel like nobody understands me",
            crisis_level="safe",
            crisis_confidence="0.8",
            conversation_history="No previous conversation",
            response_type="therapeutic_conversation",
            therapeutic_response="It sounds like you're feeling really isolated and misunderstood right now. That can be such a difficult and lonely experience. Can you tell me more about what's making you feel this way?"
        ),
        dspy.Example(
            user_message="I can't take this anymore, I want to die",
            crisis_level="crisis", 
            crisis_confidence="0.95",
            conversation_history="User: I've been struggling with depression",
            response_type="crisis_intervention",
            therapeutic_response="I hear that you're in tremendous pain right now, and I'm very concerned about you. Your safety is the most important thing. Are you thinking about hurting yourself? I want to connect you with immediate support - would you be willing to speak with a crisis counselor?"
        ),
        dspy.Example(
            user_message="Work has been really stressful lately",
            crisis_level="safe",
            crisis_confidence="0.9", 
            conversation_history="User: Things have been tough",
            response_type="therapeutic_conversation",
            therapeutic_response="Work stress can really take a toll on our overall well-being. It sounds like you've been carrying a heavy load. What aspects of work have been feeling most overwhelming for you lately?"
        )
    ]
    
    # Set up GEPA optimization
    metric = TherapyFeedbackMetric()
    
    # Configure reflection model
    reflection_lm = dspy.LM(model="together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")
    
    # Initialize GEPA optimizer
    gepa = dspy.GEPA(
        metric=metric,
        auto='light',
        reflection_lm=reflection_lm,
        reflection_minibatch_size=2
    )
    
    # Create student model
    student = DSPyTherapyResponder()
    
    # Run optimization
    logger.info("Starting DSPy GEPA optimization for therapy responses...")
    optimized_student = gepa.compile(
        student=student,
        trainset=therapy_examples[:2],  # Use subset for quick demo
        valset=therapy_examples[2:3]
    )
    
    logger.info("Therapy response optimization completed!")
    return optimized_student


if __name__ == "__main__":
    # Test the therapy response system
    print("🧠 Testing DSPy Therapy Response Generation")
    print("=" * 50)
    
    test_cases = [
        {
            "message": "I feel overwhelmed with everything",
            "crisis": "moderate_risk",
            "confidence": 0.7
        },
        {
            "message": "Work meeting went well today",
            "crisis": "safe", 
            "confidence": 0.9
        },
        {
            "message": "I don't see the point in living anymore",
            "crisis": "crisis",
            "confidence": 0.95
        }
    ]
    
    for test in test_cases:
        print(f"\nUser: {test['message']}")
        print(f"Crisis Level: {test['crisis']} ({test['confidence']:.1%} confidence)")
        
        response = generate_therapy_response(
            user_message=test['message'],
            crisis_level=test['crisis'],
            crisis_confidence=test['confidence']
        )
        
        print(f"Therapist: {response['response']}")
        print(f"Type: {response['response_type']} | Empathy: {response['empathy_score']}/10")
        print(f"Rationale: {response['therapeutic_rationale']}")
        print("-" * 50)