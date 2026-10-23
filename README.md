# PolyPilot 🧭

> **From Problem Idea to Contest-Ready Polygon Package.**  
> An AI-powered competitive programming problem-setting platform designed for Codeforces Polygon.

---

## Overview

Creating a complete competitive programming problem for Codeforces Polygon traditionally requires manual authoring of:
- Polygon-compatible LaTeX statements and sample explanations
- Editorial and proof derivations
- Optimal reference solutions ($O(\text{optimal})$) and naive brute-force solutions ($O(\text{naive})$)
- Official `testlib.h` validators with strict constraint verification
- Custom checkers (`testlib.h`) or standard Polygon comparators
- Test generators and generator scripts (`tests.cmd` / `tests.sh`)
- Deterministic edge cases, randomized distributions, and adversarial tests
- Selected incorrect solutions for WA stress testing and slow solutions for TLE testing
- Polygon API synchronization, commit revisions, and package builds

**PolyPilot** automates this pipeline through an orchestrated workflow of AI specification agents, deterministic C++17 verification runners, and official Codeforces Polygon API integration.

---

## Current Status: Phase 1 (Foundation & UI)

- **Frontend**: React 19, TypeScript, Vite, CSS Custom Properties Design System (no Tailwind), Lucide Icons, and Monaco Editor.
- **Visual Design**: Polished SaaS interface inspired by Linear, Vercel, and GitHub. Supports both Light and Dark themes.
- **Problem Workspace**: 10 comprehensive tabs:
  1. `Overview`: Problem metadata & 4-step pipeline lifecycle
  2. `Statement`: Rendered problem preview & Polygon LaTeX source (`problem.tex`)
  3. `Editorial`: Mathematical analysis, complexity breakdowns, and correctness proofs
  4. `Solutions`: Monaco editor for Reference (`solution.cpp`), Brute Force (`slow.cpp`), WA, and TLE candidates
  5. `Validator`: Official `testlib.h` validator with bounds checklist
  6. `Checker`: Standard and custom output comparators
  7. `Generators`: Testlib generator sources and Polygon script commands
  8. `Test Cases`: Complete test suite with inspector modal
  9. `Verification`: Compilation matrix, differential stress test metrics, and runtime telemetry
  10. `Polygon`: Package sync status, revision tracking, and manifest checklist
- **BYOK AI Providers & Polygon Settings**: Configuration for Google Gemini, OpenAI, Anthropic Claude, Groq, Ollama, and Polygon API credentials.

---

## Quickstart (Frontend)

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

App will run at `http://localhost:5173/`.

### Run Checks
```bash
# Type check and lint
npm run lint

# Production bundle build
npm run build
```

---

## Roadmap

- **Phase 1**: Project foundation & professional frontend UI *(Complete)*
- **Phase 2**: Backend foundation, persistence, and AI provider integration
- **Phase 3**: Structured specification & problem artifact generation
- **Phase 4**: C++ execution, verification, stress testing, and repair workflow
- **Phase 5**: Polygon API integration and automatic package publishing
- **Phase 6**: Security hardening, deployment, and final evaluation
