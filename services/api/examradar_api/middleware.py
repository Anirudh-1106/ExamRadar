"""Request IDs, structured access logs (no bodies, no personal data), and per-client rate limits."""

import logging
import time
import uuid
from collections import defaultdict
from threading import Lock

from examradar_core.logging import request_id_var
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("examradar.access")

LIMITS = [("/v1/scam-check", 10, 60), ("/admin/login", 10, 60), ("/v1/devices", 20, 60), ("/v1", 240, 60), ("/admin", 600, 60)]


class TokenBuckets:
    """In-process limiter. With several API workers each enforces its own share; use a shared store if that matters."""

    def __init__(self) -> None:
        self.state: dict[str, tuple[float, float]] = defaultdict(lambda: (0.0, 0.0))
        self.lock = Lock()

    def allow(self, key: str, rate: int, per: float) -> bool:
        now = time.monotonic()
        with self.lock:
            tokens, last = self.state.get(key, (float(rate), now))
            tokens = min(float(rate), tokens + (now - last) * rate / per)
            if tokens < 1:
                self.state[key] = (tokens, now)
                return False
            self.state[key] = (tokens - 1, now)
            return True


buckets = TokenBuckets()


class RequestContext(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_var.set(rid)
        client = request.client.host if request.client else "unknown"
        path = request.url.path
        for prefix, rate, per in LIMITS:
            if path.startswith(prefix):
                if not buckets.allow(f"{client}:{prefix}", rate, per):
                    request_id_var.reset(token)
                    return JSONResponse({"detail": "Too many requests. Please wait a moment."}, status_code=429,
                                        headers={"Retry-After": str(per), "X-Request-ID": rid})
                break
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        ms = round((time.perf_counter() - start) * 1000, 1)
        response.headers["X-Request-ID"] = rid
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if path.startswith("/admin"):
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("Cache-Control", "no-store")
        log.info("request", extra={"data": {"rid": rid, "method": request.method, "path": path, "status": response.status_code, "ms": ms}})
        return response
