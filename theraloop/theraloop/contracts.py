# theraloop/contracts.py
from typing import Protocol, Dict, Any, List, Optional

class LMAdapter(Protocol):
    """Protocol for language model adapters"""
    def complete_with_logprobs(self, prompt: str, max_tokens: int = 256, **kw) -> Dict[str, Any]: ...

class MetricExact(Protocol):
    """Protocol for exact match metrics"""
    def __call__(self, pred: str, gold: str) -> float: ...

class MetricGrounding(Protocol):
    """Protocol for grounding score metrics"""
    def __call__(self, pred: str, sources: str) -> float: ...

class MetricLogprob(Protocol):
    """Protocol for logprob-based metrics"""
    def __call__(self, text: str, token_logprobs: List[float], inputs: Dict[str, Any], 
                 negatives: Optional[List[str]] = None) -> float: ...

class ReflectFn(Protocol):
    """Protocol for reflection functions"""
    def __call__(self, prompt: str, trace: Dict[str, Any]) -> List[str]: ...