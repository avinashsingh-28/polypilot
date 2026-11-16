/**
 * Phase 4 verification API (sandboxed execution happens in the backend worker).
 */
import { apiClient as request } from './client';

export type RunStatus = 'pending' | 'queued' | 'running' | 'passed' | 'failed' | 'cancelled';
export type RunType = 'compile' | 'validator' | 'generate' | 'reference' | 'differential' | 'stress' | 'candidate';

export interface SourceSpec {
  artifact_id?: string;
  artifact_type?: string;
  repair_id?: string;
  source?: string;
  language?: string;
  label?: string;
}

export interface ApiRun {
  id: string;
  problem_id: string;
  test_type: RunType;
  status: RunStatus;
  summary: string | null;
  error_message: string | null;
  config_params: Record<string, any> | null;
  progress: { iterations_done?: number; iterations_total?: number; current_seed?: number; counterexamples?: number; minimization_attempts?: number } | null;
  cancel_requested: boolean;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface ApiRunDetail extends ApiRun {
  report: Record<string, any> | null;
  logs: string | null;
}

export interface ApiTestCase {
  id: string;
  problem_id: string;
  test_type: string;
  input_preview: string;
  input_bytes: number;
  input_truncated: boolean;
  has_expected_output: boolean;
  is_valid: boolean;
  validation_status: 'unchecked' | 'valid' | 'invalid' | 'error';
  validation_feedback: string | null;
  generator_cmd: string | null;
  generation_meta: Record<string, any> | null;
  created_at: string;
}

export interface ApiTestCaseDetail extends ApiTestCase {
  input_data: string;
  expected_output: string | null;
}

export interface ApiCounterexample {
  id: string;
  problem_id: string;
  verification_run_id: string | null;
  kind: 'mismatch' | 'candidate_failure' | 'reference_failure' | 'brute_failure';
  input_data: string;
  minimized_input: string | null;
  ref_output: string;
  candidate_output: string;
  seed: number | null;
  details: Record<string, any> | null;
  created_at: string;
}

export interface ApiRepair {
  id: string;
  problem_id: string;
  verification_run_id: string | null;
  counterexample_id: string | null;
  artifact_id: string | null;
  retest_run_id: string | null;
  language: string;
  version: number;
  suspected_bug: string | null;
  explanation: string;
  original_code: string;
  repaired_code: string;
  status: 'proposed' | 'accepted' | 'rejected';
  created_at: string;
}

export interface ApiSandboxStatus {
  available: boolean;
  mode: string;
  image: string;
  image_present: boolean;
  server_version: string | null;
  error?: string | null;
}

export interface ApiVerificationSummary {
  latest_by_type: Record<RunType, ApiRun | null>;
  active_runs: ApiRun[];
  test_case_counts: Record<string, number>;
  counterexample_count: number;
  ai_configured: boolean;
}

const p = (id: string) => `/problems/${id}`;
const json = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });

export const verificationApi = {
  sandboxStatus: () => request<ApiSandboxStatus>('/sandbox/status'),
  summary: (pid: string) => request<ApiVerificationSummary>(`${p(pid)}/verification/summary`),

  startRun: (pid: string, test_type: RunType, config: Record<string, unknown> = {}) =>
    request<ApiRun>(`${p(pid)}/verification-runs`, json({
      test_type, config,
      idempotency_key: `${test_type}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
    })),
  listRuns: (pid: string, testType?: RunType, limit = 20) =>
    request<ApiRun[]>(`${p(pid)}/verification-runs?limit=${limit}${testType ? `&test_type=${testType}` : ''}`),
  getRun: (pid: string, rid: string) => request<ApiRunDetail>(`${p(pid)}/verification-runs/${rid}`),
  cancelRun: (pid: string, rid: string) => request<ApiRun>(`${p(pid)}/verification-runs/${rid}/cancel`, { method: 'POST' }),

  listTests: (pid: string) => request<ApiTestCase[]>(`${p(pid)}/test-cases`),
  getTest: (pid: string, tid: string) => request<ApiTestCaseDetail>(`${p(pid)}/test-cases/${tid}`),
  createTest: (pid: string, body: { input_data: string; expected_output?: string; test_type?: 'manual' | 'upload' | 'invalid'; filename?: string }) =>
    request<ApiTestCaseDetail>(`${p(pid)}/test-cases`, json(body)),
  deleteTest: (pid: string, tid: string) => request<void>(`${p(pid)}/test-cases/${tid}`, { method: 'DELETE' }),
  importSamples: (pid: string) => request<ApiTestCase[]>(`${p(pid)}/test-cases/import-samples`, { method: 'POST' }),

  listCounterexamples: (pid: string) => request<ApiCounterexample[]>(`${p(pid)}/counterexamples`),

  listRepairs: (pid: string) => request<ApiRepair[]>(`${p(pid)}/repairs`),
  proposeRepair: (pid: string, counterexample_id: string, artifact_id?: string) =>
    request<ApiRepair>(`${p(pid)}/repairs`, json({ counterexample_id, artifact_id })),
  acceptRepair: (pid: string, rid: string) => request<ApiRepair>(`${p(pid)}/repairs/${rid}/accept`, { method: 'POST' }),
  rejectRepair: (pid: string, rid: string) => request<ApiRepair>(`${p(pid)}/repairs/${rid}/reject`, { method: 'POST' }),
};

export const ACTIVE_STATUSES: RunStatus[] = ['pending', 'queued', 'running'];
export const isActive = (r?: ApiRun | null) => !!r && ACTIVE_STATUSES.includes(r.status);
