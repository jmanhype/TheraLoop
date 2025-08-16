"""
Calibrated routing with ROC analysis and dynamic threshold adjustment.
"""
import os
import json
import logging
import numpy as np
from typing import List, Tuple, Optional
from sklearn.metrics import roc_curve, auc
from ..metrics.util import safe_sum

log = logging.getLogger(__name__)

# Default threshold (can be overridden by calibration)
DEFAULT_THRESHOLD = float(os.getenv("THERALOOP_CONFIDENCE_THRESHOLD", "-50.0"))

class CalibratedRouter:
    """
    Router that uses calibrated thresholds based on ROC analysis.
    """
    
    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        self.threshold = threshold
        self.calibration_data = []
        self.is_calibrated = False
        self.roc_auc = None
        
    def should_escalate(self, token_logprobs: List[float]) -> bool:
        """
        Determine if a request should be escalated based on logprobs.
        
        Args:
            token_logprobs: List of token log probabilities
            
        Returns:
            True if request should be escalated to safe mode
        """
        confidence = safe_sum(token_logprobs)
        return confidence < self.threshold
    
    def add_calibration_sample(self, token_logprobs: List[float], was_correct: bool):
        """
        Add a sample for calibration.
        
        Args:
            token_logprobs: Token log probabilities
            was_correct: Whether the output was correct/safe
        """
        self.calibration_data.append({
            "confidence": safe_sum(token_logprobs),
            "correct": was_correct
        })
    
    def calibrate(self, target_precision: float = 0.95) -> Tuple[float, float]:
        """
        Calibrate the threshold based on collected data.
        
        Args:
            target_precision: Target precision (1 - false positive rate)
            
        Returns:
            Tuple of (new_threshold, roc_auc_score)
        """
        if len(self.calibration_data) < 100:
            log.warning(f"Insufficient calibration data: {len(self.calibration_data)} samples")
            return self.threshold, 0.0
        
        # Extract features and labels
        confidences = [d["confidence"] for d in self.calibration_data]
        labels = [1 if d["correct"] else 0 for d in self.calibration_data]
        
        # Calculate ROC curve
        fpr, tpr, thresholds = roc_curve(labels, confidences)
        self.roc_auc = auc(fpr, tpr)
        
        # Find threshold for target precision
        target_fpr = 1 - target_precision
        idx = np.where(fpr <= target_fpr)[0]
        
        if len(idx) > 0:
            # Use the threshold that gives us the highest TPR while maintaining precision
            best_idx = idx[np.argmax(tpr[idx])]
            self.threshold = thresholds[best_idx]
            self.is_calibrated = True
            
            log.info(f"Calibration complete: threshold={self.threshold:.3f}, "
                    f"AUC={self.roc_auc:.3f}, samples={len(self.calibration_data)}")
        else:
            log.warning("Could not find suitable threshold for target precision")
        
        return self.threshold, self.roc_auc
    
    def save_calibration(self, path: str):
        """Save calibration data and threshold."""
        data = {
            "threshold": self.threshold,
            "is_calibrated": self.is_calibrated,
            "roc_auc": self.roc_auc,
            "calibration_samples": len(self.calibration_data),
            "calibration_data": self.calibration_data[-1000:]  # Keep last 1000 samples
        }
        
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        
        log.info(f"Calibration saved to {path}")
    
    def load_calibration(self, path: str):
        """Load calibration data and threshold."""
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            self.threshold = data["threshold"]
            self.is_calibrated = data["is_calibrated"]
            self.roc_auc = data.get("roc_auc")
            self.calibration_data = data.get("calibration_data", [])
            
            log.info(f"Calibration loaded: threshold={self.threshold:.3f}, "
                    f"samples={len(self.calibration_data)}")
        except Exception as e:
            log.error(f"Failed to load calibration: {e}")
    
    def get_confidence_score(self, token_logprobs: List[float]) -> float:
        """
        Get confidence score for a response.
        
        Args:
            token_logprobs: Token log probabilities
            
        Returns:
            Confidence score (higher is better)
        """
        return safe_sum(token_logprobs)
    
    def get_metrics(self) -> dict:
        """Get router metrics."""
        return {
            "threshold": self.threshold,
            "is_calibrated": self.is_calibrated,
            "roc_auc": self.roc_auc,
            "calibration_samples": len(self.calibration_data)
        }

# Global router instance
router = CalibratedRouter()

def should_escalate(token_logprobs: List[float]) -> bool:
    """Legacy function for backward compatibility."""
    return router.should_escalate(token_logprobs)