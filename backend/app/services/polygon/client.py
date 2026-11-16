"""
Official Codeforces Polygon API client (https://codeforces.github.io/polygon-misc/API).

Documented behaviour implemented here:
  * URL: https://polygon.codeforces.com/api/{methodName}
  * Parameters apiKey, time (UNIX seconds; requests >5 min off are denied), apiSig.
  * apiSig = <6 random chars> + hex(SHA-512("<rand>/<methodName>?<params>#<secret>")),
    params = ALL request parameters (incl. apiKey and time, excluding apiSig) sorted
    lexicographically by name, then by value, joined as name=value with '&'.
  * JSON response {status: OK|FAILED, comment, result}; some methods return raw content.

Behaviour NOT specified by the documentation (chosen conventions, isolated here):
  * Requests are sent as HTTP POST with application/x-www-form-urlencoded bodies.
  * Values are used raw (not URL-encoded) inside the signature string; file content is
    sent as an ordinary parameter and therefore included in the signature.
  * Lowercase hex digest; the random prefix uses [a-z0-9].
"""
import hashlib
import logging
import secrets
import string
import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode, urlparse

import httpx

logger = logging.getLogger(__name__)

ALLOWED_HOST = "polygon.codeforces.com"
DEFAULT_BASE_URL = f"https://{ALLOWED_HOST}/api"
RAW_METHODS = {"problem.viewFile", "problem.viewSolution", "problem.script", "problem.testInput",
               "problem.testAnswer", "problem.viewStatementResource", "problem.package"}
# Large/secret-ish values are summarized, never logged verbatim.
BULKY_PARAMS = {"file", "testInput", "source", "legend", "input", "output", "notes", "tutorial", "scoring",
                "interaction", "testInputForStatements", "testOutputForStatements", "description",
                "testDescription", "items", "content"}
SECRET_PARAMS = {"apiKey", "apiSig", "pin"}
_RAND_ALPHABET = string.ascii_lowercase + string.digits


class PolygonError(Exception):
    """Normalized Polygon failure. `kind` is one of KINDS."""
    KINDS = ("missing_credentials", "invalid_credentials", "clock_skew", "permission_denied", "not_found",
             "rate_limited", "network", "timeout", "server_error", "invalid_request", "invalid_response",
             "ambiguous", "configuration")

    def __init__(self, kind: str, message: str, method: Optional[str] = None, http_status: Optional[int] = None):
        super().__init__(message)
        self.kind, self.message, self.method, self.http_status = kind, message, method, http_status

    def to_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "method": self.method, "http_status": self.http_status}


# ── Signing (pure functions; unit-tested with deterministic inputs) ────────────
def _str(v: Any) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def normalize_params(params: Dict[str, Any]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):  # repeated parameter (e.g. testIndex)
            out.extend((k, _str(x)) for x in v)
        else:
            out.append((k, _str(v)))
    return out


def signature_base(rand: str, method: str, pairs: Iterable[Tuple[str, str]]) -> str:
    query = "&".join(f"{k}={v}" for k, v in sorted(pairs))
    return f"{rand}/{method}?{query}"


def compute_api_sig(rand: str, method: str, pairs: Iterable[Tuple[str, str]], secret: str) -> str:
    if len(rand) != 6:
        raise ValueError("Polygon apiSig prefix must be exactly 6 characters")
    digest = hashlib.sha512(f"{signature_base(rand, method, pairs)}#{secret}".encode("utf-8")).hexdigest()
    return rand + digest


def random_prefix() -> str:
    return "".join(secrets.choice(_RAND_ALPHABET) for _ in range(6))


def summarize_params(pairs: Iterable[Tuple[str, str]]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in pairs:
        if k in SECRET_PARAMS:
            continue
        if k in BULKY_PARAMS or len(v) > 200:
            v = f"<{len(v.encode('utf-8'))} bytes sha256:{hashlib.sha256(v.encode('utf-8')).hexdigest()[:12]}>"
        if k in out:
            out[k] = out[k] if isinstance(out[k], list) else [out[k]]
            out[k].append(v)
        else:
            out[k] = v
    return out


def classify_comment(comment: str, http_status: Optional[int]) -> str:
    c = (comment or "").lower()
    if http_status == 429 or "too many" in c or "rate limit" in c:
        return "rate_limited"
    if "apikey" in c or "api key" in c:
        return "invalid_credentials"
    if "apisig" in c or "signature" in c:
        return "invalid_credentials"
    if "time" in c and ("differ" in c or "5 minutes" in c or "clock" in c):
        return "clock_skew"
    if "access" in c or "permission" in c or "rights" in c or "denied" in c or "not allowed" in c:
        return "permission_denied"
    if "not found" in c or "no such" in c or "doesn't exist" in c or "does not exist" in c:
        return "not_found"
    if http_status is not None and http_status >= 500:
        return "server_error"
    return "invalid_request"


@dataclass
class Credentials:
    api_key: str
    api_secret: str
    source: str  # "env" | "stored"

    def __repr__(self) -> str:  # never leak secrets via repr/logging
        return f"Credentials(source={self.source!r}, api_key='{self.api_key[:4]}…')"


def validate_base_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme != "https" or p.hostname != ALLOWED_HOST or p.username or p.password or p.port not in (None, 443):
        raise PolygonError("configuration", f"POLYGON_API_BASE_URL must be https://{ALLOWED_HOST}/api")
    return url.rstrip("/")


class PolygonClient:
    """Thread-safe-ish synchronous client. `on_operation` receives a secret-free record per request."""
    _clock_offset = 0.0           # server_time - local_time, learned from HTTP Date headers
    _offset_lock = threading.Lock()

    def __init__(self, creds: Optional[Credentials], base_url: str = DEFAULT_BASE_URL, *,
                 timeout: float = 60.0, transport: Optional[httpx.BaseTransport] = None,
                 min_interval: float = 0.25, max_read_retries: int = 2,
                 on_operation: Optional[Callable[[dict], None]] = None,
                 sleep: Optional[Callable[[float], None]] = None):
        if creds is None or not creds.api_key or not creds.api_secret:
            raise PolygonError("missing_credentials", "Polygon API key/secret are not configured")
        self.creds = creds
        self.base_url = validate_base_url(base_url)
        self._http = httpx.Client(timeout=httpx.Timeout(timeout, connect=10.0), transport=transport,
                                  follow_redirects=False, headers={"User-Agent": "PolyPilot/0.5"})
        self.min_interval, self.max_read_retries = min_interval, max_read_retries
        self.on_operation = on_operation
        self._sleep = sleep or (lambda sec: time.sleep(sec))
        self._last_request = 0.0

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ── request building ──
    def _now(self) -> int:
        return int(time.time() + PolygonClient._clock_offset)

    def build_request(self, method: str, params: Dict[str, Any], rand: Optional[str] = None,
                      now: Optional[int] = None) -> List[Tuple[str, str]]:
        pairs = normalize_params(params)
        pairs += [("apiKey", self.creds.api_key), ("time", str(now if now is not None else self._now()))]
        pairs.append(("apiSig", compute_api_sig(rand or random_prefix(), method, pairs, self.creds.api_secret)))
        return pairs

    def _learn_clock(self, resp: httpx.Response) -> None:
        date = resp.headers.get("date")
        if not date:
            return
        try:
            server = parsedate_to_datetime(date).timestamp()
        except (TypeError, ValueError):
            return
        with PolygonClient._offset_lock:
            PolygonClient._clock_offset = server - time.time()

    # ── main entry ──
    def call(self, method: str, params: Optional[Dict[str, Any]] = None, *, write: bool = False) -> Any:
        """Call a method. Reads are retried on transient errors; writes are never retried and
        raise kind='ambiguous' when the outcome is unknown (caller must reconcile via reads)."""
        attempts = 1 if write else 1 + self.max_read_retries
        last: Optional[PolygonError] = None
        for attempt in range(attempts):
            try:
                return self._once(method, params or {}, write)
            except PolygonError as e:
                last = e
                retryable = e.kind in ("network", "timeout", "server_error", "rate_limited", "clock_skew")
                if write or not retryable or attempt == attempts - 1:
                    raise
                self._sleep(min(8.0, (2 ** attempt) * (2.0 if e.kind == "rate_limited" else 0.5)))
        raise last  # pragma: no cover

    def _once(self, method: str, params: Dict[str, Any], write: bool) -> Any:
        wait = self.min_interval - (time.monotonic() - self._last_request)
        if wait > 0:
            self._sleep(wait)
        pairs = self.build_request(method, params)
        record = {"method": method, "params": summarize_params(pairs), "write": write,
                  "timestamp": time.time(), "status": None, "http_status": None}
        start = time.monotonic()
        try:
            self._last_request = time.monotonic()
            resp = self._http.post(f"{self.base_url}/{method}", content=urlencode(pairs).encode("ascii"),
                                   headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
        except httpx.TimeoutException:
            err = PolygonError("ambiguous" if write else "timeout",
                               "Request timed out" + (" — the write may or may not have been applied" if write else ""), method)
            self._emit(record, start, error=err)
            raise err
        except httpx.HTTPError as exc:
            # Connection refused / DNS errors before sending are not ambiguous, but we cannot always
            # tell; treat write transport errors as ambiguous to force reconciliation.
            err = PolygonError("ambiguous" if write else "network", f"Network error: {type(exc).__name__}", method)
            self._emit(record, start, error=err)
            raise err
        self._learn_clock(resp)
        record["http_status"] = resp.status_code
        try:
            result = self._parse(method, resp, write)
        except PolygonError as err:
            self._emit(record, start, error=err)
            raise
        self._emit(record, start, summary=self._summary(result))
        return result

    def _parse(self, method: str, resp: httpx.Response, write: bool) -> Any:
        ctype = resp.headers.get("content-type", "")
        body = None
        looks_json = resp.content[:1] == b"{"
        # Polygon sometimes returns its JSON {status, comment} with a text/html content type
        # (observed live on problem.testInput errors), so sniff the body as well.
        if "json" in ctype or (looks_json and (method not in RAW_METHODS or resp.status_code >= 400)):
            try:
                body = resp.json()
            except ValueError:
                body = None
        if isinstance(body, dict) and body.get("status") in ("OK", "FAILED"):
            if body["status"] == "OK":
                return body.get("result")
            comment = str(body.get("comment") or "FAILED")
            raise PolygonError(classify_comment(comment, resp.status_code), comment[:500], method, resp.status_code)
        if resp.status_code == 429:
            raise PolygonError("rate_limited", "HTTP 429 Too Many Requests", method, 429)
        if resp.status_code >= 500:
            kind = "ambiguous" if write else "server_error"
            raise PolygonError(kind, f"Polygon server error HTTP {resp.status_code}", method, resp.status_code)
        if resp.status_code >= 400:
            raise PolygonError("invalid_request", f"HTTP {resp.status_code}", method, resp.status_code)
        if method in RAW_METHODS:
            return resp.content
        raise PolygonError("ambiguous" if write else "invalid_response",
                           "Unexpected non-JSON response from Polygon", method, resp.status_code)

    @staticmethod
    def _summary(result: Any) -> str:
        if isinstance(result, (bytes, bytearray)):
            return f"<raw {len(result)} bytes>"
        if isinstance(result, list):
            return f"list[{len(result)}]"
        if isinstance(result, dict):
            return "{" + ", ".join(list(result.keys())[:8]) + "}"
        if result is None:
            return "OK"
        return str(result)[:200]

    def _emit(self, record: dict, start: float, summary: Optional[str] = None, error: Optional[PolygonError] = None):
        record["duration_ms"] = int((time.monotonic() - start) * 1000)
        record["status"] = "ok" if error is None else ("ambiguous" if error.kind == "ambiguous" else "failed")
        record["response_summary"] = summary
        if error:
            record["error_kind"], record["error_message"] = error.kind, error.message
        logger.info("polygon %s %s %sms%s", record["method"], record["status"], record["duration_ms"],
                    f" ({error.kind}: {error.message})" if error else "")
        if self.on_operation:
            try:
                self.on_operation(record)
            except Exception:  # pragma: no cover - logging must never break the call
                logger.exception("on_operation hook failed")
