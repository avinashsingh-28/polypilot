import React, { useCallback, useEffect, useState } from 'react';
import { Globe2, Key, ShieldCheck, ExternalLink, Info, Trash2, Wifi } from 'lucide-react';
import { polygonApi, PolygonStatus, PolygonTestResult } from '../api/polygon';
import { Notice, StatusBadge } from '../components/verification/shared';

const fmt = (s?: string | null) => (s ? new Date(s).toLocaleString() : '—');

export const PolygonSettingsPage: React.FC = () => {
  const [status, setStatus] = useState<PolygonStatus | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [test, setTest] = useState<PolygonTestResult | null>(null);

  const load = useCallback(() => polygonApi.status().then(setStatus).catch((e) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);

  const save = async () => {
    setBusy(true); setError(null);
    try {
      setStatus(await polygonApi.saveCredentials(apiKey.trim(), apiSecret.trim()));
      setTest(null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setApiKey(''); setApiSecret('');   // never keep secrets in component state after submit
      setBusy(false);
    }
  };

  const runTest = async () => {
    setBusy(true); setError(null);
    try { const t = await polygonApi.test(); setTest(t); setStatus(t.status); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const remove = async () => {
    setBusy(true);
    try { setStatus(await polygonApi.deleteCredentials()); setTest(null); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div style={{ maxWidth: '880px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>Codeforces Polygon Integration</h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px' }}>
          Official Polygon API credentials (API key + secret). All requests are signed with SHA-512 on the backend; the secret never reaches the browser.
        </p>
      </div>

      <div className="card" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <Wifi size={18} style={{ color: 'var(--brand-primary)' }} />
          <strong style={{ fontSize: 15 }}>Connection status</strong>
          <StatusBadge status={!status ? 'pending' : !status.configured ? 'cancelled' : status.last_test_ok ? 'passed' : status.last_test_ok === false ? 'failed' : 'queued'} />
          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            {!status ? 'Loading…' : !status.configured ? 'Not configured'
              : `Credentials from ${status.source === 'env' ? 'backend environment (.env)' : 'encrypted store'} • key ${status.key_hint}`}
          </span>
          <button className="btn btn-primary" style={{ marginLeft: 'auto', fontSize: 12 }} disabled={busy || !status?.configured} onClick={runTest}>
            <ShieldCheck size={14} /> Test connection (read-only)
          </button>
        </div>
        {status && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8, fontSize: 12, color: 'var(--text-secondary)' }}>
            <div>Last test: {fmt(status.last_test_at)} {status.last_test_kind && `(${status.last_test_kind})`}</div>
            <div>Last successful connection: {fmt(status.last_success_at)}</div>
            <div>Accessible problems: {status.accessible_problems ?? '—'}</div>
            <div>API endpoint: <code>{status.base_url}</code> (fixed)</div>
          </div>
        )}
        {test && <Notice kind={test.ok ? 'info' : 'error'}>{test.message}</Notice>}
        {!test && status?.last_test_message && status.last_test_ok === false && <Notice kind="error">{status.last_test_message}</Notice>}
        {status?.env_overrides_stored && <Notice kind="warning">Environment credentials are set and take precedence over the saved credentials.</Notice>}
      </div>

      <div className="card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <h2 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', gap: 8, alignItems: 'center' }}>
          <Key size={16} /> {status?.source === 'stored' ? 'Replace saved credentials' : 'Save credentials'}
        </h2>
        {status && !status.encryption_available && (
          <Notice kind="warning">
            Saving from this page requires <code>POLYGON_CREDENTIALS_KEY</code> (a Fernet key) in <code>backend/.env</code> — secrets are never stored in plaintext.
            Alternatively set <code>POLYGON_API_KEY</code> and <code>POLYGON_API_SECRET</code> in <code>backend/.env</code> and restart the backend.
          </Notice>
        )}
        <div className="form-group">
          <label className="form-label">Polygon API Key</label>
          <input type="text" className="form-input" autoComplete="off" spellCheck={false} value={apiKey} onChange={(e) => setApiKey(e.target.value)} placeholder="API key" />
        </div>
        <div className="form-group">
          <label className="form-label">Polygon API Secret</label>
          <input type="password" className="form-input" autoComplete="new-password" value={apiSecret} onChange={(e) => setApiSecret(e.target.value)} placeholder="Write-only — never shown again after saving" />
          <span className="form-hint">The secret is encrypted on the backend and is never returned by any API.</span>
        </div>
        {error && <Notice kind="error">{error}</Notice>}
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" disabled={busy || apiKey.trim().length < 8 || apiSecret.trim().length < 8} onClick={save}>
            <Globe2 size={14} /> Save encrypted
          </button>
          {status?.source === 'stored' && (
            <button className="btn btn-secondary" disabled={busy} onClick={remove}><Trash2 size={14} /> Remove saved credentials</button>
          )}
        </div>
      </div>

      <div className="card" style={{ padding: '20px 24px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', fontWeight: 600, color: 'var(--text-primary)' }}><Info size={16} /> Getting an API key</div>
        <ol style={{ paddingLeft: 18, marginTop: 6 }}>
          <li>Open Polygon and go to <strong>Settings → API Keys</strong>.</li>
          <li>Create a key and copy the key and secret.</li>
          <li>Enter them here (or in <code>backend/.env</code>) and run the read-only connection test.</li>
        </ol>
        <a href="https://codeforces.github.io/polygon-misc/API" target="_blank" rel="noreferrer" style={{ display: 'inline-flex', gap: 4, alignItems: 'center' }}>
          Official Polygon API documentation <ExternalLink size={12} />
        </a>
      </div>
    </div>
  );
};
