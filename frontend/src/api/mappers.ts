/**
 * Mapping functions between API (snake_case) and frontend (camelCase) Problem shapes.
 */

import type { ApiProblem, ApiProblemCreate } from '../api/client';
import type { Problem, ProblemDifficulty, ProblemStatus } from '../types/problem';

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
