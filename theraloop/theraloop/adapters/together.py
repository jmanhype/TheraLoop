from typing import Dict, Any, List
import os, requests
import json
import logging
import time
import random

logger = logging.getLogger(__name__)

TOGETHER_URL = "https://api.together.xyz/v1/chat/completions"

# Mock logic removed - we now fail fast instead of masking issues

def complete_with_logprobs(prompt: str, max_tokens: int = 256, **kw) -> Dict[str, Any]:
    api_key = os.getenv("TOGETHER_API_KEY")
    model = kw.get("model", "meta-llama/Llama-3.2-3B-Instruct-Turbo")
    temperature = kw.get("temperature", 0.2)
    stop = kw.get("stop")

    if not api_key:
        # Fail fast - no API key means we cannot function
        raise ValueError(
            "TOGETHER_API_KEY environment variable is required. "
            "Set your Together AI API key to enable crisis detection."
        )

    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "logprobs": True,
        "top_logprobs": 1,
        "stop": stop
    }
    # Retry logic with exponential backoff for rate limits
    max_retries = 3
    base_delay = 1.0
    
    for attempt in range(max_retries + 1):
        try:
            # Optional rate limiting for batch processing
            if os.getenv("TOGETHER_RATE_LIMIT", "false").lower() == "true":
                time.sleep(1)
            
            r = requests.post(TOGETHER_URL, json=payload, headers=headers, timeout=180)
            r.raise_for_status()
            break  # Success - exit retry loop
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429 and attempt < max_retries:
                # Rate limited - retry with exponential backoff
                delay = base_delay * (2 ** attempt) + random.uniform(0, 1)
                logger.warning(f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries + 1})")
                time.sleep(delay)
                continue
            else:
                # Non-retryable error or max retries exceeded
                raise
        except Exception as e:
            # Non-HTTP errors (network, timeout, etc.) - don't retry
            raise
    
    # Parse response after successful request
    data = r.json()
    choice = data["choices"][0]
    message = choice.get("message", {})
    logprobs = choice.get("logprobs", {})
    
    # Debug: Log the full logprobs structure
    logger.debug(f"Logprobs structure: {logprobs}")
    
    # Extract token logprobs from chat format
    token_logprobs = []
    if logprobs:
        # Together AI returns logprobs with 'token_logprobs' field
        if "token_logprobs" in logprobs:
            token_logprobs = logprobs["token_logprobs"]
        elif "content" in logprobs and isinstance(logprobs["content"], list):
            # Alternative format with content array
            for item in logprobs["content"]:
                if "logprob" in item:
                    token_logprobs.append(item["logprob"])
    
    # If no logprobs available, leave empty (fail explicit rather than fake)
    if not token_logprobs:
        logger.warning("No logprobs returned from Together AI API")
    
    text = message.get("content", "")
    logger.info(f"Together API response: {text[:100]}...")
    logger.debug(f"Logprobs extracted: {len(token_logprobs)} tokens")
    
    return {
        "text": text,
        "token_logprobs": token_logprobs,
        "tokens": []
    }
