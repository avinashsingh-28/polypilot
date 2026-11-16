"""
AI-assisted repair proposals (user-triggered only; one AI call per request).

Never modifies artifacts: every proposal is stored as a separate
SolutionRepair version. Accepting a proposal only queues a sandboxed re-test.
"""
import uuid
from typing import Optional, Tuple

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.artifact import ProblemArtifact
from app.models.counterexample import Counterexample
from app.models.problem import Problem
from app.models.solution_repair import SolutionRepair
from app.models.verification import VerificationRun
from app.services.ai.base import AIProvider
from app.services.verification.engine import strip_fences


class RepairError(ValueError):
    pass


def _clip(s: Optional[str], n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n…[truncated {len(s) - n} chars]"


def build_repair_prompt(spec_text: str, code: str, language: str, cx: Counterexample,
                        diagnostics: str) -> str:
    return f"""You are an expert competitive programmer debugging a solution.

## Problem specification
{_clip(spec_text, 6000)}

## Failing solution ({language})
```
{_clip(code, 20000)}
```

## Failing input
```
{_clip(cx.minimized_input or cx.input_data, 3000)}
```

## Reference (oracle) output
```
{_clip(cx.ref_output, 2000)}
```

## Failing solution output
```
{_clip(cx.candidate_output, 2000)}
```

## Diagnostics
{_clip(diagnostics, 3000)}

Note: the reference output is a candidate oracle and may itself be wrong. If you believe the
failing solution is correct and the reference is wrong, say so in "suspected_bug" and return the
original code unchanged.

Respond with a single JSON object with exactly these keys:
  "suspected_bug": one or two sentences naming the bug,
  "explanation": a short explanation of the proposed change,
  "code": the complete corrected {language} source code (no markdown fences)
"""


def resolve_failing_source(db: Session, problem: Problem, cx: Counterexample,
                           artifact_id: Optional[str], source: Optional[str], language: Optional[str]
                           ) -> Tuple[str, str, Optional[uuid.UUID]]:
    if source:
        return source, language or "cpp", None
    if artifact_id:
        art = db.query(ProblemArtifact).filter_by(id=uuid.UUID(artifact_id), problem_id=problem.id).first()
        if not art:
            raise RepairError("Artifact not found for this problem")
        return strip_fences(art.content)[0], art.language or problem.language or "cpp", art.id
    # Fall back to the candidate used by the run that produced the counterexample.
    run = db.get(VerificationRun, cx.verification_run_id) if cx.verification_run_id else None
    spec = ((run.config_params or {}).get("candidate") if run else None) or {}
    if spec.get("repair_id"):
        rep = db.query(SolutionRepair).filter_by(id=uuid.UUID(spec["repair_id"]), problem_id=problem.id).first()
        if rep:
            return rep.repaired_code, rep.language, rep.artifact_id
    if spec.get("source"):
        return spec["source"], spec.get("language") or "cpp", None
    q = db.query(ProblemArtifact).filter_by(problem_id=problem.id)
    art = q.filter_by(id=uuid.UUID(spec["artifact_id"])).first() if spec.get("artifact_id") else \
        q.filter_by(artifact_type=spec.get("artifact_type") or "").first()
    if not art:
        raise RepairError("Could not determine the failing source; pass artifact_id or source")
    return strip_fences(art.content)[0], art.language or problem.language or "cpp", art.id


async def propose_repair(db: Session, ai: AIProvider, problem: Problem, cx: Counterexample,
                         artifact_id: Optional[str] = None, source: Optional[str] = None,
                         language: Optional[str] = None) -> SolutionRepair:
    code, lang, art_id = resolve_failing_source(db, problem, cx, artifact_id, source, language)
    spec_art = db.query(ProblemArtifact).filter_by(problem_id=problem.id, artifact_type="specification").first()
    spec_text = spec_art.content if spec_art else (
        f"{problem.title}\n{problem.idea or ''}\nInput: {problem.input_format or ''}\n"
        f"Output: {problem.output_format or ''}\nConstraints: {problem.constraints_text or ''}")
    d = cx.details or {}
    diagnostics = d.get("message") or ""
    for role in ("candidate", "reference"):
        r = d.get(role) or {}
        if r.get("stderr"):
            diagnostics += f"\n{role} stderr: {r['stderr'][:1000]}"

    result = await ai.generate_json(build_repair_prompt(spec_text, code, lang, cx, diagnostics), temperature=0.2)
    if not isinstance(result, dict) or not isinstance(result.get("code"), str) or not result["code"].strip():
        raise RepairError("AI provider returned an invalid repair proposal (missing 'code')")
    repaired = strip_fences(result["code"])[0]

    version = (db.query(func.count(SolutionRepair.id))
               .filter(SolutionRepair.problem_id == problem.id).scalar() or 0) + 1
    rep = SolutionRepair(problem_id=problem.id, verification_run_id=cx.verification_run_id,
                         counterexample_id=cx.id, artifact_id=art_id, language=lang, version=version,
                         original_code=code, repaired_code=repaired,
                         suspected_bug=str(result.get("suspected_bug") or "")[:4000],
                         explanation=str(result.get("explanation") or "")[:8000], status="proposed")
    db.add(rep)
    db.commit()
    db.refresh(rep)
    return rep
