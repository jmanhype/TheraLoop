"""
Observability middleware with Prometheus metrics.
"""
import time
import logging
from typing import Callable, Dict, Any
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

log = logging.getLogger(__name__)

# Create a custom registry for TheraLoop metrics
REGISTRY = CollectorRegistry()

# Define metrics
request_count = Counter(
    'theraloop_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status'],
    registry=REGISTRY
)

request_duration = Histogram(
    'theraloop_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint'],
    registry=REGISTRY
)

active_requests = Gauge(
    'theraloop_active_requests',
    'Number of active requests',
    registry=REGISTRY
)

logprob_confidence = Histogram(
    'theraloop_logprob_confidence',
    'Distribution of logprob confidence scores',
    buckets=[-100, -50, -20, -10, -5, -2, -1, 0],
    registry=REGISTRY
)

escalation_count = Counter(
    'theraloop_escalations_total',
    'Total number of escalations to safe mode',
    registry=REGISTRY
)

gepa_generation_time = Histogram(
    'theraloop_gepa_generation_seconds',
    'GEPA generation time in seconds',
    ['generation_number'],
    registry=REGISTRY
)

pareto_front_size = Histogram(
    'theraloop_pareto_front_size',
    'Size of Pareto front at each generation',
    buckets=[1, 2, 3, 5, 8, 10, 15, 20],
    registry=REGISTRY
)

together_api_errors = Counter(
    'theraloop_together_api_errors_total',
    'Total Together API errors',
    ['error_type'],
    registry=REGISTRY
)

circuit_breaker_state = Gauge(
    'theraloop_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half-open)',
    registry=REGISTRY
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track HTTP metrics.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Track active requests
        active_requests.inc()
        
        # Start timing
        start_time = time.time()
        method = request.method
        path = request.url.path
        
        try:
            # Process request
            response = await call_next(request)
            
            # Record metrics
            duration = time.time() - start_time
            request_count.labels(
                method=method,
                endpoint=path,
                status=response.status_code
            ).inc()
            
            request_duration.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            return response
            
        except Exception as e:
            # Record error
            duration = time.time() - start_time
            request_count.labels(
                method=method,
                endpoint=path,
                status=500
            ).inc()
            
            request_duration.labels(
                method=method,
                endpoint=path
            ).observe(duration)
            
            log.error(f"Request failed: {e}")
            raise
            
        finally:
            # Decrement active requests
            active_requests.dec()

def track_logprob_confidence(confidence: float):
    """Track logprob confidence distribution."""
    logprob_confidence.observe(confidence)

def track_escalation():
    """Track escalation to safe mode."""
    escalation_count.inc()

def track_gepa_generation(generation: int, duration: float):
    """Track GEPA generation time."""
    gepa_generation_time.labels(generation_number=generation).observe(duration)

def track_pareto_front(size: int):
    """Track Pareto front size."""
    pareto_front_size.observe(size)

def track_together_error(error_type: str):
    """Track Together API errors."""
    together_api_errors.labels(error_type=error_type).inc()

def update_circuit_breaker_state(state: str):
    """Update circuit breaker state metric."""
    state_map = {"closed": 0, "open": 1, "half-open": 2}
    circuit_breaker_state.set(state_map.get(state, -1))

def get_metrics() -> bytes:
    """
    Generate Prometheus metrics.
    
    Returns:
        Metrics in Prometheus text format
    """
    return generate_latest(REGISTRY)

def get_metrics_dict() -> Dict[str, Any]:
    """
    Get metrics as a dictionary.
    
    Returns:
        Dictionary of current metric values
    """
    return {
        "active_requests": active_requests._value.get(),
        "total_requests": sum(
            request_count.labels(m, e, s)._value.get()
            for m in ["GET", "POST"]
            for e in ["/", "/optimize", "/metrics"]
            for s in [200, 500]
        ),
        "total_escalations": escalation_count._value.get(),
        "total_api_errors": sum(
            together_api_errors.labels(e)._value.get()
            for e in ["timeout", "rate_limit", "connection", "other"]
        )
    }