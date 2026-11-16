"""
Structured logging, request IDs, in-process metrics, request-size limits and security headers.
Never logs bodies, cookies, Authorization headers, prompts or secrets.
"""
import contextvars
import json
import logging
import sys
import threading
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_STD_ATTRS = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}
_REDACT = ("secret", "password", "token", "apikey", "api_key", "apisig", "authorization", "cookie")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        out = {"ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(), "level": record.levelname,
               "logger": record.name, "msg": record.getMessage(), "request_id": request_id_var.get()}
        for k, v in record.__dict__.items():
            if k not in _STD_ATTRS and not k.startswith("_"):
                out[k] = "[redacted]" if any(r in k.lower() for r in _REDACT) else v
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str)


class TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        return super().format(record)


def configure_logging(level: str = "INFO", json_logs: bool = False) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_logs else
                         TextFormatter("%(asctime)s %(levelname)s [%(request_id)s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


class Metrics:
    """Tiny in-process metrics registry (per process; exported in Prometheus text format)."""

    def __init__(self):
        self._lock = threading.Lock()
        self.requests = defaultdict(int)            # (method, route, status_class) -> count
        self.latency_sum = defaultdict(float)       # (method, route) -> seconds
        self.latency_count = defaultdict(int)
        self.counters = defaultdict(int)            # free-form named counters
        self.started = time.time()

    def observe(self, method: str, route: str, status: int, seconds: float) -> None:
        with self._lock:
            self.requests[(method, route, f"{status // 100}xx")] += 1
            self.latency_sum[(method, route)] += seconds
            self.latency_count[(method, route)] += 1

    def inc(self, name: str, n: int = 1) -> None:
        with self._lock:
            self.counters[name] += n

    def render(self, gauges: dict) -> str:
        lines = ["# TYPE polypilot_http_requests_total counter"]
        with self._lock:
            for (m, r, c), n in sorted(self.requests.items()):
                lines.append(f'polypilot_http_requests_total{{method="{m}",route="{r}",status="{c}"}} {n}')
            lines.append("# TYPE polypilot_http_request_seconds summary")
            for (m, r), total in sorted(self.latency_sum.items()):
                lines.append(f'polypilot_http_request_seconds_sum{{method="{m}",route="{r}"}} {total:.6f}')
                lines.append(f'polypilot_http_request_seconds_count{{method="{m}",route="{r}"}} {self.latency_count[(m, r)]}')
            for name, n in sorted(self.counters.items()):
                lines.append(f"polypilot_{name}_total {n}")
        for name, v in sorted(gauges.items()):
            lines.append(f"polypilot_{name} {v}")
        lines.append(f"polypilot_uptime_seconds {time.time() - self.started:.0f}")
        return "\n".join(lines) + "\n"


metrics = Metrics()
log = logging.getLogger("polypilot.http")


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_body: int):
        super().__init__(app)
        self.max_body = max_body

    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id", "")
        rid = rid if rid and len(rid) <= 64 and rid.replace("-", "").isalnum() else uuid.uuid4().hex
        token = request_id_var.set(rid)
        start = time.perf_counter()
        status = 500
        try:
            length = request.headers.get("content-length")
            if length and length.isdigit() and int(length) > self.max_body:
                status = 413
                response: Response = JSONResponse({"detail": "Request body too large"}, status_code=413)
            elif request.method in ("POST", "PUT", "PATCH") and not length and \
                    "chunked" in request.headers.get("transfer-encoding", ""):
                status = 411
                response = JSONResponse({"detail": "Content-Length required"}, status_code=411)
            else:
                response = await call_next(request)
                status = response.status_code
        except Exception:
            log.exception("unhandled error", extra={"path": request.url.path, "method": request.method})
            metrics.inc("unhandled_errors")
            response = JSONResponse({"detail": "Internal server error", "request_id": rid}, status_code=500)
            status = 500
        finally:
            elapsed = time.perf_counter() - start
            route = request.scope.get("route")
            route_path = getattr(route, "path", "unmatched")
            metrics.observe(request.method, route_path, status, elapsed)
            if status >= 500:
                log.error("request failed", extra={"method": request.method, "route": route_path, "status": status,
                                                   "duration_ms": round(elapsed * 1000, 1)})
            request_id_var.reset(token)
        response.headers["X-Request-ID"] = rid
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = response.headers.get("Cache-Control", "no-store")
        return response
