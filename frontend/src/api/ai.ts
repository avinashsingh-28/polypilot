import { apiClient } from './client';

export interface SavedKey {
  provider: string;
  key_hint: string;
  model: string;
  updated_at: string;
  last_test_ok: boolean | null;
  last_tested_at: string | null;
  last_error: string | null;
}

export interface ProviderInfo {
  id: string;
  label: string;
  description: string;
  key_url: string;
  key_placeholder: string;
  default_model: string;
  suggested_models: string[];
  saved: SavedKey | null;
}

export interface ActiveProvider {
  provider: string;
  label: string;
  model: string;
  configured: boolean;
  source: 'own' | 'server' | null;
}

export interface ProvidersOverview {
  providers: ProviderInfo[];
  active: ActiveProvider;
  selected: string | null;
  server: Omit<ActiveProvider, 'source'>;
  can_save_keys: boolean;
  server_daily_limit: number;
  calls_last_24h: number;
}

export interface KeyTestResult {
  ok: boolean;
  model: string;
  model_available: boolean | null;
  models: string[];
  error: string | null;
  saved: SavedKey;
}

const json = (method: string, body: unknown) => ({ method, body: JSON.stringify(body) });

export const aiApi = {
  overview: () => apiClient<ProvidersOverview>('/ai/providers'),
  /** apiKey undefined = keep the saved key and only change the model. */
  save: (id: string, apiKey: string | undefined, model: string) =>
    apiClient<SavedKey>(`/ai/providers/${id}`, json('PUT', { api_key: apiKey || null, model })),
  remove: (id: string) => apiClient<{ deleted: boolean; selected: string | null }>(`/ai/providers/${id}`, { method: 'DELETE' }),
  test: (id: string, model?: string) => apiClient<KeyTestResult>(`/ai/providers/${id}/test`, json('POST', { model: model || null })),
  setActive: (id: string | null) => apiClient<ActiveProvider>('/ai/active', json('PUT', { provider: id })),
};
