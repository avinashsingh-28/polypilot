"""
Individual step functions called by the pipeline.
Each function receives (ai, problem, spec) and returns
either a dict (for specification) or a string (for all other steps).
"""
from app.services.ai.base import AIProvider
from app.services.ai.prompts import (
    specification_prompt,
    statement_prompt,
    reference_solution_prompt,
    brute_force_prompt,
    validator_prompt,
    generator_prompt,
    editorial_prompt,
)


async def run_specification(ai: AIProvider, problem, spec: dict) -> dict:
    """Step 1: Generate a structured problem specification."""
    time_limit_s = float(problem.time_limit_seconds or 2.0)
    prompt = specification_prompt(
        idea=problem.idea or "",
        algorithm=problem.algorithm or "",
        constraints=problem.constraints_text or "",
        input_format=problem.input_format or "",
        output_format=problem.output_format or "",
        difficulty=problem.difficulty or "Div. 2 C",
        time_limit_s=time_limit_s,
        memory_limit_mb=problem.memory_limit_mb or 256,
    )
    result = await ai.generate_json(prompt, temperature=0.2)
    return validate_specification(result)


_SPEC_TEXT_FIELDS = ("problem_name", "legend", "formal_statement", "input_format", "output_format")


def validate_specification(spec) -> dict:
    """Structured-output validation for the AI specification. Raises AIError('invalid_response')
    instead of letting a malformed model response flow into later steps."""
    from app.services.ai.base import AIError

    def bad(msg):
        raise AIError("invalid_response", f"AI specification is malformed: {msg}")

    if not isinstance(spec, dict):
        bad(f"expected a JSON object, got {type(spec).__name__}")
    for k in _SPEC_TEXT_FIELDS:
        if not isinstance(spec.get(k), str) or not spec[k].strip():
            bad(f"'{k}' must be a non-empty string")
    if len(spec["problem_name"]) > 200 or any(c in spec["problem_name"] for c in "\r\n\u2028\u2029"):
        bad("'problem_name' must be a single line of at most 200 characters")
    samples = spec.get("samples")
    if not isinstance(samples, list) or not samples or len(samples) > 20:
        bad("'samples' must be a list of 1-20 samples")
    for i, smp in enumerate(samples):
        if not isinstance(smp, dict) or not isinstance(smp.get("input"), str) or not isinstance(smp.get("output"), str):
            bad(f"sample #{i + 1} must have string 'input' and 'output'")
    for k, lo, hi in (("time_limit_seconds", 0.25, 15), ("memory_limit_mb", 4, 1024)):
        v = spec.get(k)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi):
            bad(f"'{k}' must be a number in [{lo}, {hi}]")
    return spec


async def run_statement(ai: AIProvider, problem, spec: dict) -> str:
    """Step 2: Generate the full problem statement."""
    prompt = statement_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.3)


async def run_reference_solution(ai: AIProvider, problem, spec: dict) -> str:
    """Step 3: Generate the reference (AC) C++ solution."""
    prompt = reference_solution_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.2)


async def run_brute_force(ai: AIProvider, problem, spec: dict) -> str:
    """Step 4: Generate a brute-force C++ solution for stress testing."""
    prompt = brute_force_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.2)


async def run_validator(ai: AIProvider, problem, spec: dict) -> str:
    """Step 5: Generate a testlib validator."""
    prompt = validator_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.1)


async def run_generator(ai: AIProvider, problem, spec: dict) -> str:
    """Step 6: Generate a testlib test generator."""
    prompt = generator_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.2)


async def run_editorial(ai: AIProvider, problem, spec: dict) -> str:
    """Step 7: Generate the editorial."""
    prompt = editorial_prompt(spec)
    return await ai.generate_text(prompt, temperature=0.4)

