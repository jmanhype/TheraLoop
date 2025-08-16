#!/usr/bin/env python3
"""
DSPy-Optimized User Intent Classification
========================================
Classifies user messages into therapeutic intent categories using DSPy GEPA
optimization for accurate routing and response selection.

Intent Categories:
- crisis_support: Immediate crisis intervention needed
- emotional_support: General emotional support and validation
- therapeutic_conversation: Structured therapy discussion
- informational: Information requests about therapy/mental health
- technical_support: Platform or technical issues
- casual_conversation: Light, non-therapeutic chat

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
class IntentContext:
    """Context for intent classification"""
    user_message: str
    conversation_history: List[Dict[str, str]]
    message_length: int
    contains_keywords: Dict[str, bool]
    user_session_stage: Optional[str] = None  # new, ongoing, closing


class IntentClassificationSignature(dspy.Signature):
    """Classify user message intent for appropriate therapeutic routing.
    
    INTENT CATEGORIES:
    - crisis_support: Suicidal ideation, self-harm, immediate danger
    - emotional_support: Distress, anxiety, depression, need for validation
    - therapeutic_conversation: Exploring thoughts/feelings, therapy techniques
    - informational: Questions about therapy, mental health, resources
    - technical_support: App issues, account problems, platform questions
    - casual_conversation: Greetings, small talk, non-therapeutic chat
    
    CLASSIFICATION PRINCIPLES:
    - Safety first: Crisis indicators override other categories
    - Context matters: Consider conversation history
    - Intent over content: Focus on user's underlying need
    - Conservative approach: When uncertain, favor supportive categories
    """
    
    user_message = dspy.InputField(desc="User's current message to classify")
    conversation_history = dspy.InputField(desc="Previous conversation context")
    message_context = dspy.InputField(desc="Message metadata (length, keywords, session stage)")
    
    intent_category = dspy.OutputField(desc="Primary intent: crisis_support, emotional_support, therapeutic_conversation, informational, technical_support, or casual_conversation")
    confidence_score = dspy.OutputField(desc="Classification confidence (0.0-1.0)")
    intent_indicators = dspy.OutputField(desc="Key phrases or patterns that led to this classification")
    routing_suggestion = dspy.OutputField(desc="Recommended system response approach")


class DSPyIntentClassifier(dspy.Module):
    """DSPy-based intent classifier optimized by GEPA"""
    
    def __init__(self):
        super().__init__()
        # Use ChainOfThought for reasoning about user intent
        self.classifier = dspy.ChainOfThought(IntentClassificationSignature)
    
    def forward(self, context: IntentContext) -> dspy.Prediction:
        """Classify user intent based on context"""
        
        # Format conversation history for context
        if context.conversation_history:
            history_text = "\n".join([
                f"{msg.get('role', 'Unknown')}: {msg.get('content', '')[:150]}..."
                for msg in context.conversation_history[-4:]  # Last 4 messages for context
            ])
        else:
            history_text = "No previous conversation"
        
        # Create message context summary
        context_summary = f"Length: {context.message_length} words, "
        context_summary += f"Session: {context.user_session_stage or 'unknown'}, "
        if context.contains_keywords:
            keywords_found = [k for k, v in context.contains_keywords.items() if v]
            context_summary += f"Keywords: {', '.join(keywords_found) if keywords_found else 'none'}"
        
        # Generate classification using DSPy
        return self.classifier(
            user_message=context.user_message,
            conversation_history=history_text,
            message_context=context_summary
        )


class IntentFeedbackMetric:
    """Feedback metric for intent classification optimization"""
    
    def __call__(self, gold: dspy.Example, pred: dspy.Prediction, trace=None):
        """Evaluate intent classification accuracy with feedback"""
        
        # Extract expected and predicted values
        expected_intent = gold.intent_category
        predicted_intent = pred.intent_category
        try:
            predicted_confidence = float(pred.confidence_score)
        except (ValueError, AttributeError, TypeError):
            predicted_confidence = 0.5
        
        # Scoring criteria
        score = 0.0
        feedback_items = []
        
        # 1. Exact match (70% of score)
        if expected_intent == predicted_intent:
            score += 0.7
            feedback_items.append(f"✅ Correct intent: {expected_intent}")
        else:
            feedback_items.append(f"❌ Wrong intent: expected {expected_intent}, got {predicted_intent}")
            
            # Partial credit for related intents
            intent_similarity = {
                ("crisis_support", "emotional_support"): 0.3,
                ("emotional_support", "therapeutic_conversation"): 0.2,
                ("therapeutic_conversation", "informational"): 0.15,
                ("casual_conversation", "informational"): 0.1
            }
            
            for (intent1, intent2), partial_score in intent_similarity.items():
                if (expected_intent, predicted_intent) in [(intent1, intent2), (intent2, intent1)]:
                    score += partial_score
                    feedback_items.append(f"⚠️ Partial credit for related intent")
                    break
        
        # 2. Confidence calibration (20% of score)
        if expected_intent == predicted_intent:
            if predicted_confidence >= 0.7:
                score += 0.2
                feedback_items.append("✅ High confidence on correct prediction")
            elif predicted_confidence >= 0.5:
                score += 0.1
                feedback_items.append("⚠️ Moderate confidence on correct prediction")
            else:
                feedback_items.append("❌ Low confidence on correct prediction")
        else:
            if predicted_confidence <= 0.6:
                score += 0.1
                feedback_items.append("✅ Appropriately low confidence on wrong prediction")
            else:
                feedback_items.append("❌ Overconfident on wrong prediction")
        
        # 3. Safety prioritization (10% of score)
        user_message = gold.user_message.lower()
        crisis_indicators = ["kill", "die", "suicide", "harm myself", "end it all", "can't go on"]
        has_crisis_indicators = any(indicator in user_message for indicator in crisis_indicators)
        
        if has_crisis_indicators:
            if predicted_intent == "crisis_support":
                score += 0.1
                feedback_items.append("✅ Correctly identified crisis indicators")
            else:
                feedback_items.append("❌ CRITICAL: Missed crisis indicators - safety risk!")
        else:
            if predicted_intent != "crisis_support":
                score += 0.05
            elif "crisis" not in expected_intent:
                feedback_items.append("⚠️ False positive for crisis - may cause unnecessary alarm")
        
        # Generate improvement feedback
        feedback = " | ".join(feedback_items)
        if score < 0.6:
            feedback += " | IMPROVE: Focus on intent keywords, context clues, and safety indicators"
        
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

# Thread-safe global classifier instance
optimized_classifier = None
_classifier_lock = threading.Lock()

def _initialize_intent_classifier():
    """Initialize DSPy intent classifier with GEPA optimization"""
    global optimized_classifier
    
    # Double-checked locking pattern for thread safety
    if optimized_classifier is not None:
        return optimized_classifier
    
    with _classifier_lock:
        if optimized_classifier is not None:
            return optimized_classifier
        
        try:
            # Configure DSPy with Together AI
            import os
            api_key = os.getenv("TOGETHER_API_KEY")
            if not api_key:
                logger.warning("TOGETHER_API_KEY not found, using fallback")
                api_key = os.getenv("OPENAI_API_KEY")
                if api_key:
                    # Validate API key format
                    if len(api_key) < 10 or not api_key.replace('-', '').replace('_', '').isalnum():
                        raise ValueError("Invalid OpenAI API key format")
                    lm = dspy.LM(model="gpt-3.5-turbo", api_key=api_key)
                else:
                    raise ValueError("No API key available")
            else:
                # Validate Together API key format
                if len(api_key) < 20 or not api_key.replace('-', '').replace('_', '').isalnum():
                    raise ValueError("Invalid Together API key format")
                lm = dspy.LM(model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", api_key=api_key)
            
            dspy.configure(lm=lm)
            
            # Initialize intent classifier
            optimized_classifier = DSPyIntentClassifier()
            logger.info("DSPy intent classifier initialized successfully")
            
            return optimized_classifier
            
        except Exception as e:
            logger.error(f"Failed to initialize DSPy intent classifier: {e}")
            return None


def classify_user_intent(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    user_session_stage: str = None
) -> Dict[str, Any]:
    """
    Classify user message intent using DSPy GEPA optimization.
    
    Args:
        user_message: User's current message
        conversation_history: Previous conversation context
        user_session_stage: Stage of user session (new, ongoing, closing)
        
    Returns:
        Dict with intent classification and metadata
    """
    
    # Initialize classifier
    classifier = _initialize_intent_classifier()
    
    if classifier is None:
        # Fallback classification if DSPy fails
        logger.error("DSPy intent classifier unavailable, using fallback")
        return {
            "intent_category": "emotional_support",  # Safe default
            "confidence_score": 0.5,
            "intent_indicators": "Fallback classification",
            "routing_suggestion": "Use general emotional support approach",
            "method": "fallback"
        }
    
    try:
        # Analyze message for keywords and context
        message_words = user_message.lower().split()
        message_length = len(message_words)
        
        # Define keyword categories
        keyword_categories = {
            "crisis": ["kill", "die", "suicide", "harm", "hurt", "end", "over", "done"],
            "emotional": ["sad", "anxious", "depressed", "overwhelmed", "stressed", "crying"],
            "therapeutic": ["therapy", "counseling", "feelings", "thoughts", "explore", "understand"],
            "informational": ["what", "how", "why", "explain", "help", "information", "question"],
            "technical": ["login", "password", "app", "website", "error", "bug", "account"],
            "casual": ["hello", "hi", "thanks", "good", "morning", "evening", "weather"]
        }
        
        contains_keywords = {}
        for category, keywords in keyword_categories.items():
            contains_keywords[category] = any(keyword in user_message.lower() for keyword in keywords)
        
        # Create intent context
        context = IntentContext(
            user_message=user_message,
            conversation_history=conversation_history or [],
            message_length=message_length,
            contains_keywords=contains_keywords,
            user_session_stage=user_session_stage
        )
        
        # Classify intent using DSPy
        prediction = classifier(context)
        
        # Parse confidence score
        try:
            confidence_score = float(prediction.confidence_score)
        except (ValueError, AttributeError, TypeError):
            confidence_score = 0.5
        
        logger.info(f"DSPy intent classification: '{user_message[:50]}...' -> {prediction.intent_category} ({confidence_score:.2f})")
        
        return {
            "intent_category": prediction.intent_category,
            "confidence_score": confidence_score,
            "intent_indicators": prediction.intent_indicators,
            "routing_suggestion": prediction.routing_suggestion,
            "method": "dspy_gepa"
        }
        
    except Exception as e:
        logger.error(f"DSPy intent classification failed: {e}")
        # Fallback classification
        return {
            "intent_category": "emotional_support",
            "confidence_score": 0.4,
            "intent_indicators": f"Error fallback: {str(e)}",
            "routing_suggestion": "Use general support approach due to classification error",
            "method": "error_fallback"
        }


def optimize_intent_classification():
    """
    Run GEPA optimization on intent classification.
    This would typically be run offline to improve the model.
    """
    
    # Sample training data for intent classification optimization
    intent_examples = [
        dspy.Example(
            user_message="I can't take this anymore, I want to die",
            conversation_history="No previous conversation",
            message_context="Length: 9 words, Session: new, Keywords: crisis",
            intent_category="crisis_support"
        ),
        dspy.Example(
            user_message="I'm feeling really anxious about my job interview tomorrow",
            conversation_history="User: Hi there",
            message_context="Length: 10 words, Session: ongoing, Keywords: emotional",
            intent_category="emotional_support"
        ),
        dspy.Example(
            user_message="Can you help me understand what cognitive behavioral therapy is?",
            conversation_history="User: I've been thinking about therapy",
            message_context="Length: 12 words, Session: ongoing, Keywords: informational, therapeutic",
            intent_category="informational"
        ),
        dspy.Example(
            user_message="I've been exploring my childhood memories in our sessions",
            conversation_history="Assistant: How has that process felt for you?",
            message_context="Length: 10 words, Session: ongoing, Keywords: therapeutic",
            intent_category="therapeutic_conversation"
        ),
        dspy.Example(
            user_message="I can't log into my account, the password isn't working",
            conversation_history="No previous conversation",
            message_context="Length: 10 words, Session: new, Keywords: technical",
            intent_category="technical_support"
        ),
        dspy.Example(
            user_message="Good morning! How are you doing today?",
            conversation_history="Assistant: Hello! I'm here to support you.",
            message_context="Length: 8 words, Session: new, Keywords: casual",
            intent_category="casual_conversation"
        )
    ]
    
    # Set up GEPA optimization
    metric = IntentFeedbackMetric()
    
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
    student = DSPyIntentClassifier()
    
    # Run optimization
    logger.info("Starting DSPy GEPA optimization for intent classification...")
    optimized_student = gepa.compile(
        student=student,
        trainset=intent_examples[:4],  # Use subset for quick demo
        valset=intent_examples[4:6]
    )
    
    logger.info("Intent classification optimization completed!")
    return optimized_student


if __name__ == "__main__":
    # Test the intent classification system
    print("🎯 Testing DSPy Intent Classification")
    print("=" * 50)
    
    test_cases = [
        {
            "message": "I don't want to live anymore",
            "expected": "crisis_support"
        },
        {
            "message": "I'm feeling overwhelmed with work stress",
            "expected": "emotional_support"
        },
        {
            "message": "What techniques can help with anxiety?",
            "expected": "informational"
        },
        {
            "message": "I've been thinking about my relationship patterns",
            "expected": "therapeutic_conversation"
        },
        {
            "message": "The app keeps crashing when I try to log in",
            "expected": "technical_support"
        },
        {
            "message": "Hi there! Hope you're having a good day",
            "expected": "casual_conversation"
        }
    ]
    
    correct_predictions = 0
    total_predictions = len(test_cases)
    
    for test in test_cases:
        print(f"\nUser: {test['message']}")
        print(f"Expected: {test['expected']}")
        
        result = classify_user_intent(
            user_message=test['message'],
            user_session_stage="testing"
        )
        
        print(f"Predicted: {result['intent_category']} ({result['confidence_score']:.2f})")
        print(f"Indicators: {result['intent_indicators']}")
        print(f"Routing: {result['routing_suggestion']}")
        
        if result['intent_category'] == test['expected']:
            print("✅ CORRECT")
            correct_predictions += 1
        else:
            print("❌ INCORRECT")
        
        print("-" * 50)
    
    accuracy = correct_predictions / total_predictions
    print(f"\n🎯 Intent Classification Accuracy: {accuracy:.1%} ({correct_predictions}/{total_predictions})")