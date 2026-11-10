/**
 * Mapping functions between API (snake_case) and frontend (camelCase) Problem shapes.
 */

import type { ApiProblem, ApiProblemCreate, ApiArtifact } from '../api/client';
import type { Problem, ProblemDifficulty, ProblemStatus, ProblemArtifacts, ProblemSolution } from '../types/problem';

/** Convert an API problem response to the frontend Problem shape. */
export function apiProblemToFrontend(p: ApiProblem): Problem {
  return {
    id: p.id,
    title: p.title,
    slug: p.slug,
    shortIdea: p.idea ?? '',
    difficulty: (p.difficulty ?? 'Div. 2 B (1100-1400)') as ProblemDifficulty,
    intendedAlgorithm: p.algorithm ?? '',
    constraints: p.constraints_text ?? '',
    // API stores seconds as a decimal; frontend uses milliseconds
    timeLimitMs: p.time_limit_seconds != null ? Math.round(p.time_limit_seconds * 1000) : 2000,
    memoryLimitMb: p.memory_limit_mb ?? 256,
    preferredLanguage: p.language ?? 'cpp',
    status: (p.status ?? 'draft') as ProblemStatus,
    createdAt: p.created_at,
    updatedAt: p.updated_at,
    // artifacts and verification remain undefined until Phase 3 agent fills them
    artifacts: undefined,
    verification: undefined,
    polygon: undefined,
  };
}

/** Convert a frontend "new problem" form submission to an API create payload. */
export function frontendToApiCreate(
  data: Pick<
    Problem,
    | 'title'
    | 'shortIdea'
    | 'difficulty'
    | 'intendedAlgorithm'
    | 'constraints'
    | 'timeLimitMs'
    | 'memoryLimitMb'
    | 'preferredLanguage'
  >
): ApiProblemCreate {
  return {
    title: data.title,
    idea: data.shortIdea || undefined,
    algorithm: data.intendedAlgorithm || undefined,
    constraints_text: data.constraints || undefined,
    time_limit_seconds: data.timeLimitMs ? data.timeLimitMs / 1000 : undefined,
    memory_limit_mb: data.memoryLimitMb || undefined,
    difficulty: data.difficulty || undefined,
    language: data.preferredLanguage || 'cpp',
  };
}

/** Convert a list of API artifacts into the frontend ProblemArtifacts tree. */
export function apiArtifactsToFrontend(
  artifacts: ApiArtifact[],
  fallbackProblem?: Partial<Problem>
): ProblemArtifacts | undefined {
  if (!artifacts || artifacts.length === 0) return undefined;

  const artMap: Record<string, string> = {};
  for (const a of artifacts) {
    artMap[a.artifact_type] = a.content;
  }

  let spec: any = {};
  if (artMap['specification']) {
    try {
      spec = JSON.parse(artMap['specification']);
    } catch (e) {
      console.warn('Failed to parse specification artifact:', e);
    }
  }

  const rawStatement = artMap['statement'] || '';
  const refCode = artMap['reference_solution'] || artMap['solution_main'] || '';
  const bruteCode = artMap['brute_force'] || artMap['solution_brute'] || '';
  const valCode = artMap['validator'] || '';
  const genCode = artMap['generator'] || '';
  const editorialText = artMap['editorial'] || '';

  const samples = Array.isArray(spec.samples) && spec.samples.length > 0
    ? spec.samples.map((s: any) => ({
        input: String(s.input || '').trim(),
        output: String(s.output || '').trim(),
        explanation: s.explanation || '',
      }))
    : [];

  const solutions: ProblemSolution[] = [];
  if (refCode) {
    solutions.push({
      id: 'sol-ref',
      filename: 'solution.cpp',
      tag: 'main',
      description: 'Accepted reference implementation (C++17)',
      code: refCode,
      language: 'cpp',
    });
  }
  if (bruteCode) {
    solutions.push({
      id: 'sol-brute',
      filename: 'slow.cpp',
      tag: 'accepted',
      description: 'Brute-force verification solution',
      code: bruteCode,
      language: 'cpp',
    });
  }

  const tests = samples.map((s: any, idx: number) => ({
    id: idx + 1,
    type: 'sample' as const,
    inputPreview: s.input,
    outputPreview: s.output,
    validated: true,
  }));

  return {
    statement: {
      legend: rawStatement || spec.legend || spec.formal_statement || fallbackProblem?.shortIdea || '',
      inputFormat: spec.input_format || 'Standard input format.',
      outputFormat: spec.output_format || 'Standard output format.',
      samples,
      notes: spec.notes || '',
    },
    editorial: {
      approach: editorialText || spec.correctness_reasoning || spec.intended_algorithm || '',
      complexityTime: spec.complexity?.time || 'O(N log N)',
      complexitySpace: spec.complexity?.space || 'O(N)',
      proof: spec.correctness_reasoning || '',
    },
    solutions,
    validator: {
      filename: 'validator.cpp',
      code: valCode || '// Validator pending generation\n',
      boundsNotes: spec.constraints ? JSON.stringify(spec.constraints, null, 2) : '',
    },
    checker: {
      filename: 'checker.cpp',
      type: 'standard',
      standardName: 'ncmp.cpp',
      code: '// Standard testlib tokens checker (ncmp.cpp)\n#include "testlib.h"\n\nint main(int argc, char * argv[]) {\n    setName("compare ordered sequences of tokens");\n    registerTestlibCmd(argc, argv);\n    while (!ans.seekEof()) {\n        std::string j = ans.readToken();\n        std::string p = ouf.readToken();\n        if (j != p) quitf(_wa, "expected \'%s\', found \'%s\'", compress(j).c_str(), compress(p).c_str());\n    }\n    quitf(_ok, "output matches reference");\n}\n',
    },
    generators: genCode
      ? [
          {
            filename: 'gen_random.cpp',
            code: genCode,
            scriptCommands: [
              'gen_random small 1 > tests/01.in',
              'gen_random large 42 > tests/02.in',
              'gen_random edge 99 > tests/03.in',
            ],
          },
        ]
      : [],
    tests,
  };
}
