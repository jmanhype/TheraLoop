
from __future__ import annotations
import os, uuid, time
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from .redact import redact_text

SAFE_MODE = os.getenv("SAFE_MODE", "0") == "1"

class RedactionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id") or str(uuid.uuid4())
        if SAFE_MODE:
            try:
                body = await request.body()
                _ = redact_text(body.decode("utf-8")[:4000], use_presidio=False)
            except Exception:
                pass
        start = time.perf_counter()
        response = await call_next(request)
        _ = rid; _ = start  # placeholders for potential logging
        return response
