"""
Token-based output comparison (whitespace-insensitive, token-exact).

Default mode: tokens must match exactly; any amount/kind of whitespace between
tokens and trailing whitespace/newlines are ignored.
Optional float mode: tokens that both parse as real numbers *and* contain a
decimal point or exponent are compared with an absolute/relative tolerance.
Integer tokens are always compared exactly so "1000000" != "1000001".
"""
import math
import re
from dataclasses import dataclass, asdict
from typing import Optional

_REAL = re.compile(r"^[+-]?(\d+\.\d*|\.\d+|\d+)([eE][+-]?\d+)?$")


@dataclass
class ComparisonResult:
    matched: bool
    message: str
    token_index: Optional[int] = None
    expected_token: Optional[str] = None
    actual_token: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def _is_real_literal(tok: str) -> bool:
    return bool(_REAL.match(tok)) and any(c in tok for c in ".eE")


def _short(tok: Optional[str]) -> Optional[str]:
    if tok is None:
        return None
    return tok if len(tok) <= 64 else tok[:61] + "..."


class TokenComparator:
    def __init__(self, float_tolerance: Optional[float] = None):
        self.float_tolerance = float_tolerance

    def compare(self, actual: str, expected: str) -> ComparisonResult:
        a, e = actual.split(), expected.split()
        for i in range(min(len(a), len(e))):
            if a[i] == e[i]:
                continue
            if self.float_tolerance is not None and _is_real_literal(a[i]) and _is_real_literal(e[i]):
                x, y = float(a[i]), float(e[i])
                if math.isfinite(x) and math.isfinite(y):
                    diff = abs(x - y)
                    if diff <= self.float_tolerance or diff <= self.float_tolerance * abs(y):
                        continue
            return ComparisonResult(False, f"Token #{i + 1} differs: expected '{_short(e[i])}', found '{_short(a[i])}'",
                                    i + 1, _short(e[i]), _short(a[i]))
        if len(a) != len(e):
            i = min(len(a), len(e))
            return ComparisonResult(
                False, f"Token count differs: expected {len(e)} tokens, found {len(a)}",
                i + 1, _short(e[i]) if i < len(e) else None, _short(a[i]) if i < len(a) else None)
        return ComparisonResult(True, f"{len(e)} tokens match")
