/**
 * Phase 5 Polygon API (backend-only signing; secrets never reach the browser).
 */
import { apiClient as request } from './client';

export interface PolygonStatus {
  configured: boolean;
  source: 'env' | 'stored' | null;
  key_hint: string | null;
  env_overrides_stored: boolean;
  encryption_available: boolean;
  base_url: string;
  last_test_at: string | null;
  last_test_ok: boolean | null;
  last_test_kind: string | null;
  last_test_message: string | null;
  last_success_at: string | null;
  accessible_problems: number | null;
}

export interface PolygonTestResult {
  ok: boolean;
  kind: string;
  message: string;
  accessible_problems: number | null;
  status: PolygonStatus;
}

export interface RemoteProblem {
  id: number;
  name: string;
  owner: string;
  accessType: string;
  revision: number;
  workingCopyRevision?: number;
  modified: boolean;
}

export interface PolygonIntegration {
  id: string;
  external_problem_id: string | null;
  sync_status: string;
  remote_name: string | null;
  remote_owner: string | null;
  access_type: string | null;
  remote_revision: number | null;
  working_copy_revision: number | null;
  remote_modified: boolean | null;
  link_mode: string | null;
  pending_create: { name: string; requested_at: string } | null;
  last_remote_check_at: string | null;
  last_synced_at: string | null;
  last_commit: Record<string, any> | null;
  last_build: Record<string, any> | null;
}

export interface PlanItem {
  key: string;
  type: string;
  label: string;
  local_hash: string;
  local_version: number | null;
  remote_name: string | null;
  remote_index: number | null;
  verification: { status: string; detail?: string; run_id?: string };
  blocked: string | null;
  warnings: string[];
  state: string;
  action: 'create' | 'update' | 'unchanged' | 'conflict' | 'blocked' | 'upload';
  reason: string | null;
  changes?: any;
}

export interface SyncPlan {
  items: PlanItem[];
  warnings: string[];
  fingerprint: string;
  counts: Record<string, number>;
  remote_checked: boolean;
  remote_problem: RemoteProblem | null;
  remote_only_tests: number[];
  not_supported: string[];
}

export interface SyncRun {
  id: string;
  kind: string;
  status: string;
  scope: Record<string, any> | null;
  summary: string | null;
  result: Record<string, any> | null;
  plan?: SyncPlan | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  operations?: { method: string; write: boolean; params: Record<string, any>; status: string; http_status: number | null;
    duration_ms: number | null; response_summary: string | null; error_kind: string | null; error_message: string | null; created_at: string }[];
}

export interface PolygonOverview {
  problem: { id: string; title: string; slug: string; time_limit_seconds: number; memory_limit_mb: number };
  integration: PolygonIntegration | null;
  item_states: { item_key: string; status: string; remote_name: string | null; remote_index: number | null; error: string | null; uploaded_at: string | null }[];
  runs: SyncRun[];
}

export interface SyncScope {
  include?: string[];
  solutions?: string[];
  tags?: Record<string, string>;
  allow_unverified?: string[];
  overwrite_remote?: string[];
}

export interface BuildPreflight {
  remote_problem: RemoteProblem;
  readiness_issues: { type: string; message: string }[];
  hard_cautions: { type: string; message: string }[];
  phase4: Record<string, string>;
  items_not_confirmed: string[];
  issues: string[];
  ready: boolean;
}

export interface BuildStatus {
  packages: { id: number; revision: number; creationTimeSeconds: number; state: string; comment: string; type: string }[];
  last_build: Record<string, any>;
  state: 'not_started' | 'submitted' | 'building' | 'built' | 'failed' | 'unknown';
}

const post = (body: unknown): RequestInit => ({ method: 'POST', body: JSON.stringify(body) });
const p = (id: string) => `/problems/${id}/polygon`;

export const polygonApi = {
  status: () => request<PolygonStatus>('/polygon/status'),
  saveCredentials: (api_key: string, api_secret: string) =>
    request<PolygonStatus>('/polygon/credentials', { method: 'PUT', body: JSON.stringify({ api_key, api_secret }) }),
  deleteCredentials: () => request<PolygonStatus>('/polygon/credentials', { method: 'DELETE' }),
  test: () => request<PolygonTestResult>('/polygon/test', { method: 'POST' }),
  listProblems: (name?: string) => request<RemoteProblem[]>(`/polygon/problems${name ? `?name=${encodeURIComponent(name)}` : ''}`),

  overview: (pid: string) => request<PolygonOverview>(p(pid)),
  create: (pid: string, name: string) => request<PolygonIntegration>(`${p(pid)}/create`, post({ name, confirm: true })),
  reconcileCreate: (pid: string) => request<PolygonIntegration>(`${p(pid)}/reconcile-create`, { method: 'POST' }),
  link: (pid: string, polygon_problem_id: string, confirm_name: string) =>
    request<PolygonIntegration>(`${p(pid)}/link`, post({ polygon_problem_id, confirm_name })),
  unlink: (pid: string) => request<PolygonIntegration>(`${p(pid)}/unlink`, { method: 'POST' }),
  refresh: (pid: string) => request<Record<string, any>>(`${p(pid)}/refresh`, { method: 'POST' }),

  preview: (pid: string, scope: SyncScope) => request<SyncPlan>(`${p(pid)}/preview`, post(scope)),
  dryRun: (pid: string, scope: SyncScope) => request<SyncRun>(`${p(pid)}/dry-run`, post(scope)),
  sync: (pid: string, dry_run_id: string, confirm_problem_id: string) =>
    request<SyncRun>(`${p(pid)}/sync`, post({ dry_run_id, confirm_problem_id })),
  runs: (pid: string) => request<SyncRun[]>(`${p(pid)}/runs`),
  run: (pid: string, rid: string) => request<SyncRun>(`${p(pid)}/runs/${rid}`),

  updateWorkingCopy: (pid: string, confirm_problem_id: string) =>
    request<Record<string, any>>(`${p(pid)}/working-copy/update`, post({ confirm_problem_id })),
  discardWorkingCopy: (pid: string, confirm_problem_id: string, confirm_text: string) =>
    request<Record<string, any>>(`${p(pid)}/working-copy/discard`, post({ confirm_problem_id, confirm_text })),
  commit: (pid: string, confirm_problem_id: string, message: string, minor_changes: boolean) =>
    request<Record<string, any>>(`${p(pid)}/commit`, post({ confirm_problem_id, message, minor_changes })),
  preflight: (pid: string) => request<BuildPreflight>(`${p(pid)}/build/preflight`),
  build: (pid: string, confirm_problem_id: string, full: boolean, verify: boolean, acknowledge_issues: boolean) =>
    request<BuildStatus>(`${p(pid)}/build`, post({ confirm_problem_id, full, verify, acknowledge_issues })),
  buildStatus: (pid: string) => request<BuildStatus>(`${p(pid)}/build/status`),
};
