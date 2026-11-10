"""
Individual step functions called by the pipeline.
Each function receives (ai, problem, spec) and returns
either a dict (for specification) or a string (for all other steps).
"""
import json
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
    if not isinstance(result, dict):
        raise ValueError(f"Specification step returned non-dict: {type(result)}")
    return result


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

