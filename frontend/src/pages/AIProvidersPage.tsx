import React, { useEffect, useState } from 'react';
import { Cpu, Info } from 'lucide-react';
import { apiClient } from '../api/client';
import { Notice, StatusBadge } from '../components/verification/shared';

interface AIStatus {
  provider: string;
  model: string;
  configured: boolean;
  supported_providers: string[];
  timeout_sec: number;
  max_output_tokens: number;
  daily_limit: number;
  calls_last_24h: number;
  note: string;
}

/** Real, read-only AI provider status. Keys are configured on the server only (never in the browser). */
export const AIProvidersPage: React.FC = () => {
  const [status, setStatus] = useState<AIStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { apiClient<AIStatus>('/ai/status').then(setStatus).catch((e) => setError(e.message)); }, []);

  return (
    <div style={{ maxWidth: 880, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div>
        <h1 style={{ fontSize: 20, fontWeight: 700, color: 'var(--text-primary)' }}>AI Provider</h1>
        <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
          The AI provider used for generation and repair proposals is configured by the server administrator.
        </p>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {!status && !error && <div role="status" style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Loading…</div>}
      {status && (
        <div className="card" style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
            <Cpu size={18} style={{ color: 'var(--brand-primary)' }} />
            <strong style={{ fontSize: 15, textTransform: 'capitalize' }}>{status.provider}</strong>
            <StatusBadge status={status.configured ? 'passed' : 'failed'} />
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{status.configured ? 'API key configured on server' : 'No API key configured'}</span>
          </div>
          <dl style={{ display: 'grid', gridTemplateColumns: 'max-content 1fr', gap: '6px 16px', fontSize: 13, margin: 0 }}>
            <dt style={{ color: 'var(--text-muted)' }}>Model</dt><dd style={{ margin: 0 }}><code>{status.model}</code></dd>
            <dt style={{ color: 'var(--text-muted)' }}>Request timeout</dt><dd style={{ margin: 0 }}>{status.timeout_sec}s</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Max output tokens</dt><dd style={{ margin: 0 }}>{status.max_output_tokens}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Your AI calls (24h)</dt><dd style={{ margin: 0 }}>{status.calls_last_24h} / {status.daily_limit}</dd>
            <dt style={{ color: 'var(--text-muted)' }}>Supported providers</dt><dd style={{ margin: 0 }}>{status.supported_providers.join(', ')}</dd>
          </dl>
          {!status.configured && <Notice kind="warning">Set <code>GEMINI_API_KEY</code> in <code>backend/.env</code> and restart the backend to enable generation.</Notice>}
        </div>
      )}
      <div className="card" style={{ padding: '16px 20px', fontSize: 13, color: 'var(--text-secondary)', display: 'flex', gap: 8 }}>
        <Info size={16} style={{ flexShrink: 0, marginTop: 2 }} />
        <span>Bring-your-own-key and additional providers (OpenAI, Anthropic, Groq, Ollama) are <strong>not implemented</strong>. Custom endpoints are intentionally not accepted from the browser (SSRF protection).</span>
      </div>
    </div>
  );
};
