/**
 * PolyPilot API Client
 * Thin typed wrapper around the FastAPI backend REST API.
 */

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000/api/v1';

// ─── Raw API response shapes (snake_case, matching FastAPI schemas) ───────────

export interface ApiProblem {
  id: string;
  title: string;
  slug: string;
  idea: string | null;
  algorithm: string | null;
  constraints_text: string | null;
  input_format: string | null;
  output_format: string | null;
  time_limit_seconds: number | null;
  memory_limit_mb: number | null;
  difficulty: string | null;
  language: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface ApiProblemListResponse {
  items: ApiProblem[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiProblemCreate {
  title: string;
  idea?: string;
  algorithm?: string;
  constraints_text?: string;
  input_format?: string;
  output_format?: string;
  time_limit_seconds?: number;
  memory_limit_mb?: number;
  difficulty?: string;
  language?: string;
  slug?: string;
}

export interface ApiProblemUpdate {
  title?: string;
  idea?: string;
  algorithm?: string;
  constraints_text?: string;
  input_format?: string;
  output_format?: string;
  time_limit_seconds?: number;
  memory_limit_mb?: number;
  difficulty?: string;
  language?: string;
  status?: string;
}

export interface ApiArtifact {
  id: string;
  problem_id: string;
  artifact_type: string;
  name: string | null;
  content: string;
  language: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ApiArtifactCreate {
  artifact_type: string;
  name?: string;
  content: string;
  language?: string;
}

// ─── Generic fetch helper ─────────────────────────────────────────────────────

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BASE_URL}${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body?.detail ?? detail;
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;

  return res.json() as Promise<T>;
}

export const apiClient = request;

// ─── Generation API ───────────────────────────────────────────────────────────

export interface ApiGenerationStepLog {
  step: number;
  key: string;
  name: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  timestamp: string;
  error?: string;
}

export interface ApiGenerationStatus {
  job_id: string;
  problem_id: string;
  status: 'running' | 'completed' | 'failed' | 'pending';
  current_step: number;
  total_steps: number;
  current_step_name: string | null;
  steps_log: ApiGenerationStepLog[];
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export const generationApi = {
  start(problemId: string): Promise<{ job_id: string; problem_id: string; message: string }> {
    return request<{ job_id: string; problem_id: string; message: string }>(
      `/problems/${problemId}/generate`,
      { method: 'POST' }
    );
  },

  status(problemId: string): Promise<ApiGenerationStatus> {
    return request<ApiGenerationStatus>(`/problems/${problemId}/generation-status`);
  },

  regenerateStep(problemId: string, step: string): Promise<{ artifact_type: string; message: string }> {
    return request<{ artifact_type: string; message: string }>(
      `/problems/${problemId}/regenerate-step`,
      {
        method: 'POST',
        body: JSON.stringify({ step }),
      }
    );
  },
};

// ─── Problems API ─────────────────────────────────────────────────────────────

export const problemsApi = {
  list(limit = 50, offset = 0): Promise<ApiProblemListResponse> {
    return request<ApiProblemListResponse>(
      `/problems?limit=${limit}&offset=${offset}`
    );
  },

  get(id: string): Promise<ApiProblem> {
    return request<ApiProblem>(`/problems/${id}`);
  },

  create(payload: ApiProblemCreate): Promise<ApiProblem> {
    return request<ApiProblem>('/problems', {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },

  update(id: string, payload: ApiProblemUpdate): Promise<ApiProblem> {
    return request<ApiProblem>(`/problems/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(payload),
    });
  },

  delete(id: string): Promise<void> {
    return request<void>(`/problems/${id}`, { method: 'DELETE' });
  },

  listArtifacts(problemId: string): Promise<ApiArtifact[]> {
    return request<ApiArtifact[]>(`/problems/${problemId}/artifacts`);
  },

  createArtifact(problemId: string, payload: ApiArtifactCreate): Promise<ApiArtifact> {
    return request<ApiArtifact>(`/problems/${problemId}/artifacts`, {
      method: 'POST',
      body: JSON.stringify(payload),
    });
  },
};

// ─── Health API ───────────────────────────────────────────────────────────────

export interface ApiHealth {
  status: string;
  version: string;
  environment: string;
}

export const healthApi = {
  check(): Promise<ApiHealth> {
    return fetch(`${BASE_URL.replace('/api/v1', '')}/health`)
      .then(r => r.json()) as Promise<ApiHealth>;
  },
};
