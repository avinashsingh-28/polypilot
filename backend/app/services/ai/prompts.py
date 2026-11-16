"""
Prompt templates for every generation step.

Each template accepts a dict of variables and returns a fully-formed string.
The model is instructed to return structured JSON for steps that need it,
and plain text / code for the later artefact steps.
"""


def specification_prompt(idea: str, algorithm: str, constraints: str,
                          input_format: str, output_format: str,
                          difficulty: str, time_limit_s: float,
                          memory_limit_mb: int) -> str:
    return f"""You are an expert competitive-programming problem-setter working on Codeforces Polygon.

A problem setter has provided the following raw idea:

IDEA: {idea or "(not provided)"}
INTENDED ALGORITHM: {algorithm or "(to be determined)"}
CONSTRAINTS: {constraints or "(to be determined)"}
INPUT FORMAT HINT: {input_format or "(to be determined)"}
OUTPUT FORMAT HINT: {output_format or "(to be determined)"}
DIFFICULTY: {difficulty or "Div. 2 C"}
TIME LIMIT: {time_limit_s} seconds
MEMORY LIMIT: {memory_limit_mb} MB

Your task: produce a **complete, rigorous problem specification** as a single JSON object with this exact schema:

{{
  "problem_name": "Short catchy name (3-6 words)",
  "legend": "One-paragraph story/legend (2-4 sentences, no math yet)",
  "formal_statement": "Precise mathematical problem description",
  "input_format": "Exact input format description (mention every variable)",
  "output_format": "Exact output format description",
  "constraints": {{
    "n_max": <integer or null>,
    "other": ["list of additional constraint strings"]
  }},
  "time_limit_seconds": {time_limit_s},
  "memory_limit_mb": {memory_limit_mb},
  "intended_algorithm": "Algorithm name and brief description",
  "complexity": {{
    "time": "O(...) with explanation",
    "space": "O(...) with explanation"
  }},
  "correctness_reasoning": "2-3 sentences justifying correctness of the approach",
  "samples": [
    {{
      "input": "exact sample input string",
      "output": "exact sample output string",
      "explanation": "step-by-step explanation"
    }}
  ],
  "edge_cases": ["list of important edge cases to test"],
  "notes": "Any special judging notes (e.g. multiple valid answers, epsilon comparison)"
}}

Rules:
- Return ONLY the JSON object. No markdown fences, no explanation outside it.
- All string values must be valid JSON strings (escape newlines as \\n).
- Samples must be realistic and hand-verifiable.
- Do NOT invent constraints that contradict the idea; ask yourself whether the approach actually solves the stated problem.
"""


def statement_prompt(spec: dict) -> str:
    return f"""You are writing the official problem statement for a Codeforces problem.

Use the following specification:

Problem name: {spec.get('problem_name', '')}
Legend: {spec.get('legend', '')}
Formal statement: {spec.get('formal_statement', '')}
Input format: {spec.get('input_format', '')}
Output format: {spec.get('output_format', '')}
Constraints: {spec.get('constraints', '')}
Notes: {spec.get('notes', '')}

Write the FULL problem statement in Polygon/Codeforces LaTeX-compatible Markdown:

1. **[Problem Name]** — a heading using the problem name
2. **Legend** — the narrative paragraph
3. **Input** section with $\\$$n$\\$$ notation for variables
4. **Output** section
5. **Examples** — a markdown table or code-block pair for each sample
6. **Note** (if applicable)

Rules:
- Use $...$ for inline math and $$...$$ for display math.
- Keep variable names consistent between sections.
- Output only the statement text — no commentary before or after.
"""


def reference_solution_prompt(spec: dict) -> str:
    constraints = spec.get('constraints', {})
    return f"""You are writing a reference (accepted) C++ solution for a competitive programming problem.

Problem: {spec.get('problem_name', '')}
Formal statement: {spec.get('formal_statement', '')}
Intended algorithm: {spec.get('intended_algorithm', '')}
Time complexity: {spec.get('complexity', {}).get('time', '')}
Space complexity: {spec.get('complexity', {}).get('space', '')}
Constraints: n_max={constraints.get('n_max')}, {', '.join(constraints.get('other', []))}
Time limit: {spec.get('time_limit_seconds', 2)} seconds
Memory limit: {spec.get('memory_limit_mb', 256)} MB
Sample input: {spec['samples'][0]['input'] if spec.get('samples') else ''}
Expected output: {spec['samples'][0]['output'] if spec.get('samples') else ''}

Write a complete, correct, well-commented C++17 solution.

Requirements:
- Use `#include <bits/stdc++.h>` and `using namespace std;`
- Handle multiple test cases with `int t; cin >> t; while (t--) {{ ... }}`  if the problem has multiple test cases
- Optimize I/O: `ios_base::sync_with_stdio(false); cin.tie(NULL);`
- Include a brief comment block at the top explaining the approach
- The solution MUST pass within the time and memory limits
- Handle all edge cases listed: {spec.get('edge_cases', [])}

Output ONLY the C++ code. No markdown fences, no explanation.
"""


def brute_force_prompt(spec: dict) -> str:
    constraints = spec.get('constraints', {})
    return f"""You are writing a brute-force (slow but definitely correct) C++ solution for stress testing.

Problem: {spec.get('problem_name', '')}
Formal statement: {spec.get('formal_statement', '')}
Constraints: n_max={constraints.get('n_max')}, {', '.join(constraints.get('other', []))}

Write a simple brute-force C++17 solution that:
- Is obviously correct (even if O(n^3) or worse)
- Works for SMALL inputs only (n ≤ 15 is fine)
- Uses `#include <bits/stdc++.h>` and `using namespace std;`
- Has a comment block labeling it as BRUTE FORCE / SLOW SOLUTION
- Handles the same input/output format as the reference solution

Output ONLY the C++ code. No markdown fences, no explanation.
"""


def validator_prompt(spec: dict) -> str:
    constraints = spec.get('constraints', {})
    n_max = constraints.get('n_max', 200000)
    other = constraints.get('other', [])
    return f"""You are writing a testlib validator for a competitive programming problem.

Problem: {spec.get('problem_name', '')}
Input format: {spec.get('input_format', '')}
Constraints:
  - n_max = {n_max}
  - {chr(10).join(f'  - {c}' for c in other)}

Write a complete C++ testlib validator (using testlib.h) that:
- Begins with `#include "testlib.h"` and `int main(int argc, char* argv[]) {{ registerValidation(argc, argv);`
  (the testlib function is `registerValidation` — `registerValidator` does NOT exist and will not compile)
- Reads and validates EVERY value in the input, including every space (`inf.readSpace()`) and newline (`inf.readEoln()`)
- Checks ALL constraints rigorously (use `inf.readInt(lo, hi, "var_name")` etc.), including sum constraints
- Calls `inf.readEof()` at the end
- Has no output (validators don't print anything on success)
- Uses only the standard testlib API listed below (it is compiled with g++ -std=c++17 against the official testlib.h)

Testlib reference:
- `inf.readInt(lo, hi, "name")` — read and validate integer
- `inf.readLong(lo, hi, "name")` — read and validate long long  
- `inf.readToken()` / `inf.readString()` — read a token/line
- `inf.readEoln()` — read end-of-line
- `ensuref(cond, "fmt", ...)` — assert a condition

Output ONLY the C++ code. No markdown fences, no explanation.
"""


def generator_prompt(spec: dict) -> str:
    constraints = spec.get('constraints', {})
    n_max = constraints.get('n_max', 200000)
    return f"""You are writing a testlib test generator for a competitive programming problem.

Problem: {spec.get('problem_name', '')}
Constraints: n_max={n_max}, {', '.join(constraints.get('other', []))}
Input format: {spec.get('input_format', '')}

Write a C++ testlib generator that:
- Begins with `#include "testlib.h"` and `int main(int argc, char* argv[]) {{ registerGen(argc, argv, 1);`
- Takes command-line arguments: argv[1] = test_type ("small"/"large"/"edge"), argv[2] = seed
- Uses `rnd.next(lo, hi)` for random values
- Generates a valid input respecting ALL constraints
- Prints the generated test to stdout (testlib generator convention)
- Covers different modes: "small" (n≤10), "large" (n near {n_max}), "edge" (boundary cases)

Output ONLY the C++ code. No markdown fences, no explanation.
"""


def editorial_prompt(spec: dict) -> str:
    return f"""You are writing the editorial for a competitive programming problem.

Problem: {spec.get('problem_name', '')}
Formal statement: {spec.get('formal_statement', '')}
Intended algorithm: {spec.get('intended_algorithm', '')}
Time complexity: {spec.get('complexity', {}).get('time', '')}
Space complexity: {spec.get('complexity', {}).get('space', '')}
Correctness reasoning: {spec.get('correctness_reasoning', '')}
Edge cases: {spec.get('edge_cases', [])}

Write a thorough editorial in Markdown:

1. **Observations** — key mathematical or algorithmic observations
2. **Approach** — step-by-step algorithm description
3. **Correctness** — proof or intuitive justification
4. **Complexity Analysis** — time and space
5. **Implementation Notes** — pitfalls, common mistakes
6. **Alternative Approaches** (if applicable)

Use $...$ for inline math. Be precise and educational.
Output only the editorial Markdown. No commentary before or after.
"""

