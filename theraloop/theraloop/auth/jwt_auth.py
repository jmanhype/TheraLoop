"""
JWT Authentication and Rate Limiting for TheraLoop.
"""
import os
import time
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from collections import defaultdict

from fastapi import HTTPException, Request, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from pydantic import BaseModel

log = logging.getLogger(__name__)

# Configuration
SECRET_KEY = os.getenv("THERALOOP_JWT_SECRET", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# Security scheme
security = HTTPBearer()


class TokenData(BaseModel):
    """JWT token payload."""
    user_id: str
    role: str  # "user", "clinician", "admin"
    exp: Optional[datetime] = None


class JWTAuth:
    """JWT authentication handler."""
    
    def __init__(self, secret_key: str = SECRET_KEY):
        self.secret_key = secret_key
        
    def create_token(self, user_id: str, role: str) -> str:
        """Create a new JWT token."""
        payload = {
            "user_id": user_id,
            "role": role,
            "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
    
    def verify_token(self, credentials: HTTPAuthorizationCredentials = Security(security)) -> TokenData:
        """Verify and decode JWT token."""
        token = credentials.credentials
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[ALGORITHM])
            return TokenData(**payload)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expired",
                headers={"WWW-Authenticate": "Bearer"}
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    def get_current_user(self, token_data: TokenData = Security(verify_token)) -> Dict[str, Any]:
        """Get current user from token."""
        return {
            "user_id": token_data.user_id,
            "role": token_data.role
        }


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(self, requests_per_minute: int = 10):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        
    def check_rate_limit(self, key: str) -> bool:
        """Check if request is within rate limit."""
        now = time.time()
        minute_ago = now - 60
        
        # Clean old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > minute_ago
        ]
        
        # Check limit
        if len(self.requests[key]) >= self.requests_per_minute:
            return False
        
        # Record request
        self.requests[key].append(now)
        return True
    
    def get_client_id(self, request: Request) -> str:
        """Get client identifier from request."""
        # Try to get authenticated user ID
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                return f"user:{payload.get('user_id')}"
            except:
                pass
        
        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"
        
        client = request.client
        if client:
            return f"ip:{client.host}"
        
        return "unknown"


# Global instances
jwt_auth = JWTAuth()
rate_limiter = RateLimiter()


def require_auth(role: Optional[str] = None):
    """Dependency to require authentication and optionally a specific role."""
    def verify(token_data: TokenData = Security(jwt_auth.verify_token)) -> TokenData:
        if role and token_data.role != role and token_data.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required role: {role}"
            )
        return token_data
    return verify


def require_rate_limit(requests_per_minute: int = 10):
    """Dependency to enforce rate limiting."""
    limiter = RateLimiter(requests_per_minute)
    
    def check(request: Request) -> None:
        client_id = limiter.get_client_id(request)
        if not limiter.check_rate_limit(client_id):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {requests_per_minute} requests per minute.",
                headers={"Retry-After": "60"}
            )
    return check


# Audit logging
class AuditLogger:
    """Audit trail logger."""
    
    def __init__(self, log_file: str = "audit.log"):
        self.logger = logging.getLogger("audit")
        handler = logging.FileHandler(log_file)
        handler.setFormatter(
            logging.Formatter('%(asctime)s - %(message)s')
        )
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    def log_request(self, user_id: str, action: str, details: Dict[str, Any]):
        """Log an auditable action."""
        self.logger.info(
            f"USER:{user_id} ACTION:{action} DETAILS:{details}"
        )
    
    def log_escalation(self, user_id: str, request_id: str, reason: str):
        """Log an escalation event."""
        self.logger.info(
            f"ESCALATION USER:{user_id} REQUEST:{request_id} REASON:{reason}"
        )


audit_logger = AuditLogger()