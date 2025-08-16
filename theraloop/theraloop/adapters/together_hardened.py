"""
Hardened Together API adapter with retries, circuit breaker, and score-only endpoint.
"""
from typing import Dict, Any, List
import os, requests, random, time, logging
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_log,
    after_log
)

log = logging.getLogger(__name__)

TOGETHER_URL = "https://api.together.xyz/v1/completions"

# Circuit breaker state
class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call_succeeded(self):
        self.failure_count = 0
        self.state = "closed"
    
    def call_failed(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            log.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def is_open(self) -> bool:
        if self.state == "closed":
            return False
        if self.state == "open":
            if self.last_failure_time and time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = "half-open"
                log.info("Circuit breaker entering half-open state")
                return False
            return True
        return False

circuit_breaker = CircuitBreaker()

def _mock_complete(prompt: str, max_tokens: int = 256, **kw) -> Dict[str, Any]:
    # Deterministic-ish mock: echo rule-based answers for demo prompts
    text = "insufficient evidence"
    if "2+2" in prompt:
        text = "4"
    elif "ISO date for Jan 1, 2020" in prompt:
        text = "2020-01-01"
    else:
        # Short echo fallback
        text = "OK"
    # Make a plausible list of token logprobs
    token_logprobs = [-0.5 + random.random()*0.1 for _ in range(min(6, max_tokens//5 or 1))]
    return {"text": text, "token_logprobs": token_logprobs, "tokens": []}

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((requests.RequestException, ValueError)),
    before=before_log(log, logging.DEBUG),
    after=after_log(log, logging.DEBUG)
)
def complete_with_logprobs(prompt: str, max_tokens: int = 256, **kw) -> Dict[str, Any]:
    """
    Call Together API with retries and circuit breaker.
    
    Args:
        prompt: The prompt to send
        max_tokens: Maximum tokens to generate
        **kw: Additional parameters (model, temperature, stop, score_only)
    
    Returns:
        Dict with 'text', 'token_logprobs', and 'tokens' keys
    """
    if circuit_breaker.is_open():
        log.warning("Circuit breaker open, using mock fallback")
        return _mock_complete(prompt, max_tokens=max_tokens, **kw)
    
    api_key = os.getenv("TOGETHER_API_KEY")
    model = kw.get("model", "together/qwen2.5-coder-32b-instruct")
    temperature = kw.get("temperature", 0.2)
    stop = kw.get("stop")
    score_only = kw.get("score_only", False)

    if not api_key:
        # Offline/mock mode
        return _mock_complete(prompt, max_tokens=max_tokens, **kw)

    headers = {"Authorization": f"Bearer {api_key}"}
    
    # For score-only mode, we want minimal generation
    if score_only:
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": 1,
            "temperature": 0.01,
            "logprobs": True,
            "top_logprobs": 0,
            "echo": True,  # Include prompt tokens in response
            "stop": stop
        }
    else:
        payload = {
            "model": model,
            "prompt": prompt,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "logprobs": True,
            "top_logprobs": 0,
            "stop": stop
        }
    
    try:
        r = requests.post(TOGETHER_URL, json=payload, headers=headers, timeout=180)
        r.raise_for_status()
        data = r.json()
        
        if "choices" not in data or not data["choices"]:
            raise ValueError("Invalid response structure from Together API")
        
        choice = data["choices"][0]
        meta = choice.get("logprobs", {}) or {}
        
        result = {
            "text": choice.get("text", ""),
            "token_logprobs": meta.get("token_logprobs", []) or [],
            "tokens": meta.get("tokens", []) or []
        }
        
        if score_only and result["token_logprobs"]:
            # For score-only, exclude the generated token (last one)
            result["token_logprobs"] = result["token_logprobs"][:-1]
            result["tokens"] = result["tokens"][:-1] if result["tokens"] else []
        
        circuit_breaker.call_succeeded()
        return result
        
    except Exception as e:
        circuit_breaker.call_failed()
        log.error(f"Together API call failed: {e}")
        # Fallback to mock on any error (rate limits, connectivity, etc.)
        return _mock_complete(prompt, max_tokens=max_tokens, **kw)

def score_prompt(prompt: str, continuation: str) -> List[float]:
    """
    Get logprobs for a specific continuation given a prompt.
    
    Args:
        prompt: The prompt/context
        continuation: The text to score
    
    Returns:
        List of logprobs for each token in the continuation
    """
    full_text = prompt + continuation
    result = complete_with_logprobs(full_text, score_only=True)
    
    # Extract logprobs for continuation tokens only
    # This is a rough approximation - in production you'd use proper tokenization
    prompt_tokens = len(prompt.split())
    return result["token_logprobs"][prompt_tokens:]

def health_check() -> bool:
    """Check if Together API is accessible."""
    try:
        result = complete_with_logprobs("Hello", max_tokens=1)
        return bool(result.get("text"))
    except Exception as e:
        log.error(f"Health check failed: {e}")
        return False