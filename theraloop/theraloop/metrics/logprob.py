from typing import Dict, List, Optional, Callable
from .util import safe_sum

def logprob_metric(
    pred_text: str,
    token_logprobs: List[float],
    inputs: Dict,
    negatives: Optional[List[str]] = None,
    scorer_fn: Optional[Callable[[str, str], float]] = None,
) -> float:
    lp = safe_sum(token_logprobs)
    penalty = 0.0  # placeholder for negative continuation scoring
    bonus = 0.0
    if scorer_fn and "gold" in inputs:
        try:
            bonus = 0.05 * float(scorer_fn(pred_text, inputs.get("gold","")))
        except Exception:
            bonus = 0.0
    return lp + bonus - 0.5 * penalty
