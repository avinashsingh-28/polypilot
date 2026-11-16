"""
Mapping of local PolyPilot data to Polygon objects + Phase 4 verification gating.

Item keys (stable, used for remote state tracking):
  info, statement:<lang>, tutorial:<lang>, validator, checker, assign:validator, assign:checker,
  generator:<artifact_id>, solution:<artifact_id>, test:<test_case_id>
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.artifact import ProblemArtifact
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.models.verification import VerificationRun
from app.services.verification.engine import strip_fences

FILE_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,58}\.(cpp|py)$")
SOLUTION_TAGS = ("MA", "OK", "RJ", "TL", "TO", "TM", "WA", "PE", "ML", "NR", "RE")   # documented tag codes
VERDICT_TO_TAG = {"AC": "OK", "WA": "WA", "TLE": "TL", "MLE": "ML", "RE": "RE"}
NON_CODE = {"specification", "statement", "editorial", "checker", "validator", "generator"}
ALL_INCLUDE = ("info", "statement", "tutorial", "validator", "checker", "generators", "solutions", "tests")
DEFAULT_INCLUDE = ("info", "statement", "validator", "checker", "generators", "solutions", "tests")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm(text: Optional[str]) -> str:
    return (text or "").replace("\r\n", "\n").rstrip()


@dataclass
class LocalItem:
    key: str
    type: str                      # info|statement|tutorial|file|assign|solution|test
    label: str
    payload: Dict[str, Any]        # Polygon parameters to send (excluding problemId)
    local_hash: str
    local_ref: Optional[str] = None
    local_version: Optional[int] = None
    remote_name: Optional[str] = None
    remote_index: Optional[int] = None
    verification: Dict[str, Any] = field(default_factory=dict)
    blocked: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    depends_on: List[str] = field(default_factory=list)

    def public(self) -> dict:
        p = {k: (f"<{len(v.encode())} bytes>" if isinstance(v, str) and len(v) > 300 else v)
             for k, v in self.payload.items()}
        return {"key": self.key, "type": self.type, "label": self.label, "local_hash": self.local_hash,
                "local_ref": self.local_ref, "local_version": self.local_version, "remote_name": self.remote_name,
                "remote_index": self.remote_index, "verification": self.verification, "blocked": self.blocked,
                "warnings": self.warnings, "depends_on": self.depends_on, "payload_preview": p}


# ── Phase 4 verification lookup ───────────────────────────────────────────────
class Verification:
    """Finds passed Phase 4 runs that compiled exactly this source (by SHA-256)."""

    def __init__(self, db: Session, problem_id):
        self.runs = (db.query(VerificationRun).filter(VerificationRun.problem_id == problem_id)
                     .order_by(VerificationRun.created_at.desc()).limit(200).all())

    def _match(self, types, role, h):
        for r in self.runs:
            c = ((r.report or {}).get("compilations") or {}).get(role) or {}
            if r.test_type in types and c.get("source_sha256") == h:
                return r
        return None

    # Which comparison failure kinds implicate which compiled role.
    _BLAME = {
        "stress": {"gen": {"generator_failure", "validator_failure"}, "val": {"validator_failure"},
                   "reference": {"reference_failure"}, "candidate": {"candidate_failure", "output_mismatch"},
                   "checker": {"checker_failure"}},
        "differential": {"gen": {"generator_failure", "validator_failure"}, "val": {"validator_failure"},
                         "reference": {"reference_failure", "output_mismatch"},   # disagreement: either may be wrong
                         "candidate": {"brute_failure", "output_mismatch"}, "checker": {"checker_failure"}},
    }

    @classmethod
    def attributable(cls, r: VerificationRun, role: str) -> bool:
        """Does this FAILED run count against `role`? Infrastructure failures, cancellations and
        failures caused by a different artifact do not."""
        rep = r.report or {}
        if rep.get("failure_kind") in ("infrastructure", "cancelled"):
            return False
        if rep.get("failed_stage") == "compile":
            return rep.get("role") == role
        blame = cls._BLAME.get(r.test_type)
        if blame is not None:
            kinds = set(((rep.get("comparison") or {}).get("failure_kinds") or {}).keys())
            return bool(kinds & blame.get(role, set()))
        return True

    def status(self, types, role, h) -> Dict[str, Any]:
        """Newest relevant run for this exact source decides: passed → verified; a failure that is
        attributable to this role → failed; runs that failed for unrelated reasons are skipped."""
        seen_any = False
        for r in self.runs:
            c = ((r.report or {}).get("compilations") or {}).get(role) or {}
            if r.test_type not in types or c.get("source_sha256") != h:
                continue
            seen_any = True
            if r.status == "passed":
                return {"status": "verified", "run_id": str(r.id), "run_type": r.test_type, "detail": r.summary}
            if r.status == "failed" and self.attributable(r, role):
                return {"status": "failed", "run_id": str(r.id), "run_type": r.test_type, "detail": r.summary}
        if seen_any:
            return {"status": "unverified", "detail": "Matching runs exist but none passed or failed because of this artifact"}
        return {"status": "unverified", "detail": "No Phase 4 run compiled this exact source"}

    def candidate_verdict(self, h) -> Optional[str]:
        r = self._match(("candidate",), "candidate", h)
        return ((r.report or {}).get("candidate") or {}).get("verdict") if r and r.status in ("passed", "failed") else None


# ── Statement conversion ──────────────────────────────────────────────────────
_MATH = re.compile(r"(\$\$.*?\$\$|\$[^$\n]+?\$)", re.S)


def md_to_polygon(text: str) -> str:
    """Minimal Markdown→Polygon-LaTeX conversion OUTSIDE math only; math is passed through untouched."""
    out = []
    for i, part in enumerate(_MATH.split(text or "")):
        if i % 2 == 1:           # math segment — never modified
            out.append(part)
            continue
        part = re.sub(r"\*\*(.+?)\*\*", r"\\textbf{\1}", part)
        part = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\\textit{\1}", part)
        part = re.sub(r"`([^`\n]+)`", r"\\texttt{\1}", part)
        out.append(part)
    return "".join(out).strip()


_SECTION_ALIASES = [("input", "input"), ("output", "output"), ("example", None), ("sample", None),
                    ("note", "notes"), ("explanation", "notes"), ("legend", "legend"), ("statement", "legend"),
                    ("description", "legend")]
_HEADING = re.compile(r"^\s*(?:#{1,6}\s*(.+?)\s*#*\s*|\*\*\s*(.+?)\s*\*\*\s*:?)\s*$")


def parse_statement(md: str) -> Dict[str, str]:
    """Split a generated Markdown statement into Polygon sections. Example sections are dropped
    (Polygon builds examples from tests marked useInStatements)."""
    sections: Dict[str, List[str]] = {"legend": [], "input": [], "output": [], "notes": []}
    current: Optional[str] = "legend"
    seen_title = False
    for line in (md or "").replace("\r\n", "\n").split("\n"):
        m = _HEADING.match(line)
        if m:
            title = (m.group(1) or m.group(2) or "").strip().lower()
            target = "unknown"
            for alias, sec in _SECTION_ALIASES:
                if alias in title:
                    target = sec
                    break
            if target == "unknown":
                if not seen_title and not any(sections.values()):
                    seen_title = True       # problem-name heading
                    continue
                target = current
            current = target
            continue
        if current is not None:
            sections[current].append(line)
    return {k: "\n".join(v).strip() for k, v in sections.items()}


def _single_line(s: str) -> str:
    return re.sub(r"[\r\n\u2028\u2029]+", " ", s or "").strip()[:200]


# ── Local items ───────────────────────────────────────────────────────────────
def _spec(db, problem) -> dict:
    a = db.query(ProblemArtifact).filter_by(problem_id=problem.id, artifact_type="specification").first()
    try:
        return json.loads(a.content) if a else {}
    except (TypeError, ValueError):
        return {}


def _art(db, problem, t) -> Optional[ProblemArtifact]:
    a = (db.query(ProblemArtifact).filter_by(problem_id=problem.id, artifact_type=t)
         .order_by(ProblemArtifact.version.desc()).first())
    return a if a and (a.content or "").strip() else None


def _ext(art: ProblemArtifact) -> str:
    return "py" if (art.language or "").lower().startswith("py") else "cpp"


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", (s or "").lower()).strip("_")[:40] or "solution"


def info_item(problem: Problem) -> LocalItem:
    tl_ms = round(float(problem.time_limit_seconds or 2) * 1000)
    mem = int(problem.memory_limit_mb or 256)
    payload = {"inputFile": "stdin", "outputFile": "stdout", "timeLimit": tl_ms, "memoryLimit": mem}
    blocked = None
    if not 250 <= tl_ms <= 15000 or tl_ms % 50:
        blocked = f"Time limit {tl_ms} ms is invalid for Polygon (must be 250..15000 ms and divisible by 50)"
    elif not 4 <= mem <= 1024:
        blocked = f"Memory limit {mem} MB is invalid for Polygon (must be 4..1024 MB)"
    return LocalItem("info", "info", "Problem settings (time/memory limit, stdin/stdout)", payload,
                     sha(json.dumps(payload, sort_keys=True)), blocked=blocked, verification={"status": "n/a"})


def statement_item(db, problem, lang) -> Optional[LocalItem]:
    art, spec = _art(db, problem, "statement"), _spec(db, problem)
    if not art and not spec:
        return None
    parsed = parse_statement(art.content) if art else {"legend": "", "input": "", "output": "", "notes": ""}
    legend = parsed["legend"] or "\n\n".join(x for x in (spec.get("legend"), spec.get("formal_statement")) if x)
    fields = {
        "name": _single_line(spec.get("problem_name") or problem.title),
        "legend": md_to_polygon(legend),
        "input": md_to_polygon(parsed["input"] or spec.get("input_format") or ""),
        "output": md_to_polygon(parsed["output"] or spec.get("output_format") or ""),
        "notes": md_to_polygon(parsed["notes"]),
    }
    item = LocalItem(f"statement:{lang}", "statement", f"Statement ({lang})", {"lang": lang, **fields},
                     sha(json.dumps(fields, sort_keys=True)), local_ref=str(art.id) if art else None,
                     local_version=art.version if art else None, verification={"status": "n/a"})
    if not fields["legend"] or not fields["input"] or not fields["output"]:
        item.blocked = "Statement is missing legend, input or output section"
    return item


def tutorial_item(db, problem, lang) -> Optional[LocalItem]:
    art = _art(db, problem, "editorial")
    if not art:
        return None
    text = md_to_polygon(strip_fences(art.content)[0])
    return LocalItem(f"tutorial:{lang}", "tutorial", f"Tutorial / editorial ({lang}) — statement 'tutorial' field",
                     {"lang": lang, "tutorial": text}, sha(text), local_ref=str(art.id), local_version=art.version,
                     verification={"status": "n/a"})


def _source_item(key, typ, label, art: ProblemArtifact, remote_name, verification) -> LocalItem:
    src = strip_fences(art.content)[0]
    item = LocalItem(key, typ, label, {"name": remote_name, "file": src}, sha(src), local_ref=str(art.id),
                     local_version=art.version, remote_name=remote_name, verification=verification)
    if not FILE_NAME_RE.match(remote_name):
        item.blocked = f"Invalid remote file name {remote_name!r}"
    elif len(src.encode()) > get_settings().MAX_SOURCE_BYTES:
        item.blocked = "Source exceeds the maximum allowed size"
    return item


def build_local_items(db: Session, problem: Problem, scope: dict) -> List[LocalItem]:
    s = get_settings()
    include = set(scope.get("include") or DEFAULT_INCLUDE)
    unknown = include - set(ALL_INCLUDE)
    if unknown:
        raise ValueError(f"Unknown scope entries: {sorted(unknown)}")
    allow_unverified = set(scope.get("allow_unverified") or [])
    tags = scope.get("tags") or {}
    lang = s.POLYGON_STATEMENT_LANG
    ver = Verification(db, problem.id)
    items: List[LocalItem] = []

    if "info" in include:
        items.append(info_item(problem))
    if "statement" in include and (it := statement_item(db, problem, lang)):
        items.append(it)
    if "tutorial" in include and (it := tutorial_item(db, problem, lang)):
        items.append(it)

    for role, types in (("validator", ("validator",)), ("checker", ("reference", "differential", "stress", "candidate"))):
        if role not in include:
            continue
        art = _art(db, problem, role)
        if not art:
            continue
        src_h = sha(strip_fences(art.content)[0])
        v = ver.status(types, role if role == "validator" else "checker", src_h)
        if role == "checker" and "registerTestlibCmd" not in art.content:
            continue
        name = f"{role}.{_ext(art)}"
        f = _source_item(role, "file", f"{role.capitalize()} source", art, name, v)
        f.payload["type"] = "source"
        if v["status"] != "verified":
            f.blocked = f"{role.capitalize()} has not passed Phase 4 verification ({v['status']}: {v.get('detail')})"
        items.append(f)
        items.append(LocalItem(f"assign:{role}", "assign", f"Set as problem {role}", {role: name}, sha(name),
                               remote_name=name, verification=v, blocked=f.blocked, depends_on=[role]))

    if "generators" in include:
        art = _art(db, problem, "generator")
        if art:
            g = _source_item(f"generator:{art.id}", "file", "Generator source (gen)", art, f"gen.{_ext(art)}",
                             ver.status(("generate", "differential", "stress"), "gen", sha(strip_fences(art.content)[0])))
            g.payload["type"] = "source"
            if g.verification["status"] != "verified" and g.key not in allow_unverified:
                g.blocked = "Generator has not passed Phase 4 generation/validation (allow explicitly to upload anyway)"
            items.append(g)

    if "solutions" in include:
        selected = scope.get("solutions")
        arts = [a for a in db.query(ProblemArtifact).filter(ProblemArtifact.problem_id == problem.id).all()
                if a.artifact_type not in NON_CODE and (a.content or "").strip()]
        if selected is None:   # default: only the reference and brute-force solutions
            arts = [a for a in arts if a.artifact_type in ("reference_solution", "brute_force")]
        else:
            arts = [a for a in arts if str(a.id) in set(selected)]
        used_names = set()
        for a in sorted(arts, key=lambda a: (a.artifact_type != "reference_solution", a.artifact_type)):
            h = sha(strip_fences(a.content)[0])
            if a.artifact_type == "reference_solution":
                name, tag = f"main.{_ext(a)}", "MA"
                v = ver.status(("reference",), "reference", h)
            elif a.artifact_type == "brute_force":
                name, tag = f"brute.{_ext(a)}", "TO"
                v = ver.status(("differential",), "candidate", h)
            else:
                name = f"{_slug(a.name or a.artifact_type)}.{_ext(a)}"
                verdict = ver.candidate_verdict(h)
                tag = VERDICT_TO_TAG.get(verdict or "", None)
                v = ver.status(("candidate",), "candidate", h)
                if verdict:
                    v = {**v, "detail": f"Phase 4 candidate verdict: {verdict}"}
            tag = tags.get(str(a.id), tag)
            while name in used_names:
                name = name.replace(".", "_2.", 1)
            used_names.add(name)
            it = _source_item(f"solution:{a.id}", "solution", f"Solution {a.artifact_type} ({tag or 'tag?'})", a, name, v)
            it.payload["tag"] = tag
            if tag not in SOLUTION_TAGS:
                it.blocked = "Choose a Polygon solution tag (MA, OK, WA, TL, …) for this solution"
            elif v["status"] != "verified" and it.key not in allow_unverified:
                it.blocked = f"Solution not verified in Phase 4 ({v['status']}); allow explicitly to upload anyway"
            items.append(it)

    if "tests" in include:
        tests = (db.query(TestCase).filter(TestCase.problem_id == problem.id).order_by(TestCase.created_at).all())
        order = {"sample": 0, "manual": 1, "upload": 1, "generated": 2}
        valid = [t for t in tests if t.validation_status == "valid" and t.test_type != "invalid"]
        for t in sorted(valid, key=lambda t: (order.get(t.test_type, 3), t.created_at)):
            inp = t.input_data
            it = LocalItem(f"test:{t.id}", "test", f"Test ({t.test_type}{', statement example' if t.test_type == 'sample' else ''})",
                           {"testset": s.POLYGON_TESTSET, "testInput": inp, "testUseInStatements": t.test_type == "sample"},
                           sha(norm(inp)), local_ref=str(t.id), verification={"status": "verified", "detail": "Accepted by Phase 4 validator"})
            if len(inp.encode()) > s.MAX_INPUT_BYTES:
                it.blocked = "Test input too large"
            items.append(it)
    return items
