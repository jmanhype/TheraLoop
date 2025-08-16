#!/usr/bin/env python3
"""
DSPy Built-in Ensemble for Crisis Detection
==========================================
Uses DSPy's native ensemble functionality to combine multiple
crisis detection programs with majority voting.

Components:
1. Multiple Crisis Detection Programs
2. Built-in DSPy Ensemble with majority voting
3. Confidence aggregation and human review triggers

Author: TheraLoop Team
"""

import dspy
import logging
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

try:
    import numpy as np
except ImportError:
    # Fallback if numpy not available
    class NumpyFallback:
        @staticmethod
        def mean(values):
            return sum(values) / len(values) if values else 0.0
    np = NumpyFallback()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class EnsembleContext:
    """Context for ensemble prediction"""
    user_message: str
    conversation_history: List[Dict[str, str]]
    user_session_metadata: Dict[str, Any]


class ConservativeCrisisSignature(dspy.Signature):
    """Conservative crisis detection with safety-first approach"""
    user_text = dspy.InputField(desc="User's message to analyze for crisis indicators")
    classification = dspy.OutputField(desc="Crisis level: crisis, moderate_risk, or safe")
    confidence = dspy.OutputField(desc="Confidence in classification (0.0-1.0)")

class ContextAwareCrisisSignature(dspy.Signature):
    """Context-aware crisis detection considering conversation flow"""
    user_text = dspy.InputField(desc="User's message to analyze with context awareness")
    classification = dspy.OutputField(desc="Crisis level: crisis, moderate_risk, or safe")
    confidence = dspy.OutputField(desc="Confidence in classification (0.0-1.0)")


class CrisisDetectionProgram(dspy.Module):
    """Individual crisis detection program for ensemble"""
    
    def __init__(self, approach: str = "standard"):
        super().__init__()
        
        if approach == "conservative":
            signature = ConservativeCrisisSignature
        elif approach == "context_aware":
            signature = ContextAwareCrisisSignature
        else:
            # Standard approach
            from theraloop.serving.gepa_detection import CrisisDetectionSignature
            signature = CrisisDetectionSignature
        
        self.predictor = dspy.ChainOfThought(signature)
        self.approach = approach
    
    def forward(self, user_text: str) -> dspy.Prediction:
        return self.predictor(user_text=user_text)


class DSPyEnsemble:
    """DSPy built-in ensemble for crisis detection"""
    
    def __init__(self):
        self.ensemble = None
        self.confidence_threshold = 0.7  # Threshold for human review
        self.initialized = False
        
    def _initialize_ensemble(self):
        """Initialize DSPy built-in ensemble with multiple crisis detection programs"""
        if self.initialized:
            return
        
        try:
            # Configure DSPy
            import os
            api_key = os.getenv("TOGETHER_API_KEY")
            if not api_key:
                raise ValueError("TOGETHER_API_KEY required for ensemble")
            
            # Use primary model for all programs
            primary_lm = dspy.LM(model="together_ai/meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo", api_key=api_key)
            dspy.configure(lm=primary_lm)
            
            # Create multiple crisis detection programs with different approaches
            programs = [
                CrisisDetectionProgram(approach="standard"),
                CrisisDetectionProgram(approach="conservative"), 
                CrisisDetectionProgram(approach="context_aware")
            ]
            
            # Create DSPy ensemble optimizer with majority voting
            from dspy.teleprompt.ensemble import Ensemble
            ensemble_optimizer = Ensemble(reduce_fn=dspy.majority)
            
            # Compile the ensemble (this returns the ensemble as a single program)
            self.ensemble = ensemble_optimizer.compile(programs)
            
            self.initialized = True
            logger.info("DSPy built-in ensemble initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize DSPy ensemble: {e}")
            self.initialized = False
    
    def predict(self, context: EnsembleContext) -> Dict[str, Any]:
        """Generate ensemble prediction using DSPy's built-in ensemble"""
        
        self._initialize_ensemble()
        
        if not self.initialized:
            logger.error("Ensemble not initialized, using fallback")
            return self._fallback_prediction(context.user_message)
        
        try:
            # Use DSPy's built-in ensemble (compiled ensemble acts like a single program)
            ensemble_prediction = self.ensemble(user_text=context.user_message)
            
            # Parse ensemble output
            try:
                confidence = float(ensemble_prediction.confidence)
            except (ValueError, AttributeError, TypeError):
                confidence = 0.5
            
            classification = ensemble_prediction.classification
            
            # Determine if human review needed
            human_review = confidence < self.confidence_threshold
            
            logger.info(f"DSPy ensemble prediction: {context.user_message[:50]}... -> {classification} ({confidence:.2f})")
            
            return {
                'classification': classification,
                'confidence': confidence,
                'should_escalate': classification in ['crisis', 'moderate_risk'],
                'human_review_required': human_review,
                'ensemble_reasoning': "DSPy ensemble with 3 programs - majority vote",
                'method': 'dspy_native_ensemble'
            }
            
        except Exception as e:
            logger.error(f"DSPy ensemble prediction failed: {e}")
            return self._fallback_prediction(context.user_message)
    
    
    def _fallback_prediction(self, user_message: str) -> Dict[str, Any]:
        """Simple fallback when all models fail"""
        
        # Basic keyword-based crisis detection
        crisis_keywords = ['kill', 'die', 'suicide', 'harm myself', 'end it all', 'cant take', 'over']
        has_crisis_keywords = any(keyword in user_message.lower() for keyword in crisis_keywords)
        
        if has_crisis_keywords:
            classification = 'moderate_risk'  # Conservative fallback
            confidence = 0.6
        else:
            classification = 'safe'
            confidence = 0.5
        
        logger.warning(f"Using basic fallback for: {user_message[:50]}... -> {classification}")
        
        return {
            'classification': classification,
            'confidence': confidence,
            'should_escalate': classification in ['crisis', 'moderate_risk'],
            'human_review_required': True,
            'ensemble_reasoning': "Basic keyword fallback due to model failures",
            'individual_predictions': {},
            'method': 'keyword_fallback'
        }


# Global ensemble instance
global_ensemble = None

def get_ensemble() -> DSPyEnsemble:
    """Get or create global ensemble instance"""
    global global_ensemble
    
    if global_ensemble is None:
        global_ensemble = DSPyEnsemble()
    
    return global_ensemble


def ensemble_crisis_detection(
    user_message: str,
    conversation_history: List[Dict[str, str]] = None,
    user_session_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Perform ensemble crisis detection using multiple DSPy models.
    
    Args:
        user_message: User's current message
        conversation_history: Previous conversation context
        user_session_metadata: Additional user session information
        
    Returns:
        Dict with ensemble prediction and metadata
    """
    
    # Create ensemble context
    context = EnsembleContext(
        user_message=user_message,
        conversation_history=conversation_history or [],
        user_session_metadata=user_session_metadata or {}
    )
    
    # Get ensemble prediction
    ensemble = get_ensemble()
    result = ensemble.predict(context)
    
    return result


if __name__ == "__main__":
    # Test the ensemble system
    print("🔬 Testing DSPy Multi-Model Ensemble")
    print("=" * 50)
    
    test_cases = [
        {
            "message": "I want to end my life",
            "expected": "crisis",
            "description": "Direct suicidal statement"
        },
        {
            "message": "I can't handle this stress anymore",
            "expected": "moderate_risk",
            "description": "Emotional distress"
        },
        {
            "message": "This deadline is killing me",
            "expected": "safe",
            "description": "Metaphorical expression"
        },
        {
            "message": "What coping strategies work for anxiety?",
            "expected": "safe",
            "description": "Informational question"
        }
    ]
    
    for test in test_cases:
        print(f"\nTest: {test['description']}")
        print(f"User: {test['message']}")
        print(f"Expected: {test['expected']}")
        
        result = ensemble_crisis_detection(
            user_message=test['message'],
            user_session_metadata={"test_case": True}
        )
        
        print(f"Ensemble: {result['classification']} ({result['confidence']:.2f})")
        print(f"Human Review: {'Yes' if result['human_review_required'] else 'No'}")
        print(f"Method: {result['method']}")
        print(f"Reasoning: {result['ensemble_reasoning']}")
        
        if result['classification'] == test['expected']:
            print("✅ CORRECT")
        else:
            print(f"❌ INCORRECT (expected {test['expected']})")
        
        print("-" * 50)
    
    print("\n🎯 Ensemble testing completed!")