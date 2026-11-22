import React, { useCallback, useEffect, useState } from 'react';
import { CheckCircle2, Cpu, ExternalLink, KeyRound, Lock, PlugZap, Server, Trash2, XCircle, Zap } from 'lucide-react';
import { aiApi, KeyTestResult, ProviderInfo, ProvidersOverview } from '../api/ai';
import { Notice } from '../components/verification/shared';
import './ai-providers.css';

/** Users add their own API keys for any supported provider. Keys go to the server once, are stored
 *  encrypted, and are never sent back to the browser (only the last 4 characters are shown). */
export const AIProvidersPage: React.FC = () => {
  const [data, setData] = useState<ProvidersOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const load = useCallback(() => aiApi.overview().then(setData).catch((e) => setError(e.message)), []);
  useEffect(() => { void load(); }, [load]);

  const useServer = async () => {
    setError(null);
    try { await aiApi.setActive(null); await load(); } catch (e) { setError((e as Error).message); }
  };

  const active = data?.active;
  return (
    <div className="aip">
      <header>
        <h1>AI Providers</h1>
        <p>Bring your own API key for any provider below. Keys are encrypted on the server and never shown again —
          only the last 4 characters are displayed. Generation and repair run on the provider you select.</p>
      </header>

      {error && <Notice kind="error">{error}</Notice>}
      {!data && !error && <div role="status" className="aip-muted">Loading…</div>}

      {data && (
        <section className="card aip-current">
          <div className="aip-current-icon">{active?.source === 'own' ? <Zap size={20} /> : active?.source === 'server' ? <Server size={20} /> : <PlugZap size={20} />}</div>
          <div className="aip-current-body">
            <span className="aip-eyebrow">Currently using</span>
            {active?.configured ? (
              <strong>{active.label} · <code>{active.model}</code></strong>
            ) : (
              <strong>Nothing yet — add an API key below to enable generation</strong>
            )}
            <span className="aip-muted">
              {active?.source === 'own' && 'Your own key · no daily limit from PolyPilot (your provider\'s limits apply)'}
              {active?.source === 'server' && `Server default key · ${data.calls_last_24h} / ${data.server_daily_limit} calls used in the last 24h`}
            </span>
          </div>
          {active?.source === 'own' && data.server.configured && (
            <button className="btn btn-secondary aip-sm" onClick={useServer}>Use server default</button>
          )}
        </section>
      )}

      {data && !data.can_save_keys && (
        <Notice kind="warning">Saving keys is disabled on this server: no encryption key is configured
          (<code>AI_CREDENTIALS_KEY</code>). Ask the administrator.</Notice>
      )}

      {data && (
        <div className="aip-grid">
          {data.providers.map((p) => (
            <ProviderCard key={p.id} p={p} selected={data.selected === p.id} canSave={data.can_save_keys}
              open={editing === p.id} onOpen={() => setEditing(editing === p.id ? null : p.id)}
              onChanged={async () => { await load(); }} onError={setError} />
          ))}
        </div>
      )}

      <p className="aip-foot"><Lock size={13} /> Requests go only to each provider's official endpoint, chosen by the
        server — custom URLs are not accepted. Usage is billed by the provider to the key's owner.</p>
    </div>
  );
};

const MARKS: Record<string, string> = {
  gemini: 'G', anthropic: 'C', openai: 'AI', deepseek: 'DS', groq: 'GQ', mistral: 'M', xai: 'X',
  openrouter: 'OR', together: 'T', fireworks: 'FW', cerebras: 'CB',
};

interface CardProps {
  p: ProviderInfo;
  selected: boolean;
  canSave: boolean;
  open: boolean;
  onOpen: () => void;
  onChanged: () => Promise<void>;
  onError: (m: string | null) => void;
}

const ProviderCard: React.FC<CardProps> = ({ p, selected, canSave, open, onOpen, onChanged, onError }) => {
  const [key, setKey] = useState('');
  const [model, setModel] = useState(p.saved?.model ?? p.default_model);
  const [busy, setBusy] = useState<string | null>(null);
  const [test, setTest] = useState<KeyTestResult | null>(null);
  const saved = p.saved;

  useEffect(() => { setModel(p.saved?.model ?? p.default_model); }, [p.saved?.model, p.default_model]);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label); onError(null);
    try { await fn(); } catch (e) { onError(`${p.label}: ${(e as Error).message}`); } finally { setBusy(null); }
  };

  const save = () => run('save', async () => {
    await aiApi.save(p.id, key.trim() || undefined, model.trim());
    setKey('');                     // never keep the secret in component state after submit
    const t = await aiApi.test(p.id).catch(() => null);
    setTest(t);
    await onChanged();
  });
  const doTest = () => run('test', async () => { setTest(await aiApi.test(p.id, model.trim())); await onChanged(); });
  const remove = () => run('remove', async () => {
    if (!window.confirm(`Delete your saved ${p.label} API key?`)) return;
    await aiApi.remove(p.id); setTest(null); await onChanged();
  });
  const select = () => run('select', async () => { await aiApi.setActive(p.id); await onChanged(); });

  const status = !saved ? null : saved.last_test_ok === true ? 'ok' : saved.last_test_ok === false ? 'bad' : 'untested';
  const modelOptions = Array.from(new Set([...(test?.models ?? []), ...p.suggested_models, p.default_model]));

  return (
    <article className={`card aip-card${selected ? ' is-active' : ''}`}>
      <div className="aip-card-head">
        <div className="aip-logo" aria-hidden="true">{MARKS[p.id] ?? p.label.slice(0, 2)}</div>
        <div className="aip-card-title">
          <h3>{p.label}</h3>
          <p>{p.description}</p>
        </div>
        {selected ? <span className="aip-pill aip-pill-active"><CheckCircle2 size={12} /> Active</span>
          : saved ? <span className="aip-pill">Saved</span> : null}
      </div>

      {saved && (
        <dl className="aip-meta">
          <dt>Key</dt><dd><code>{saved.key_hint}</code></dd>
          <dt>Model</dt><dd><code>{saved.model}</code></dd>
          <dt>Status</dt>
          <dd className={`aip-status aip-status-${status}`}>
            {status === 'ok' && <><CheckCircle2 size={13} /> Key works</>}
            {status === 'bad' && <><XCircle size={13} /> {saved.last_error ?? 'Test failed'}</>}
            {status === 'untested' && 'Not tested yet'}
          </dd>
        </dl>
      )}

      {open && (
        <div className="aip-editor">
          <label className="form-label" htmlFor={`key-${p.id}`}>{saved ? 'Replace API key (leave blank to keep)' : 'API key'}</label>
          <input id={`key-${p.id}`} className="form-input" type="password" autoComplete="off" spellCheck={false}
            placeholder={p.key_placeholder || 'Paste your API key'} value={key} maxLength={512}
            onChange={(e) => setKey(e.target.value)} />
          <label className="form-label" htmlFor={`model-${p.id}`}>Model</label>
          <input id={`model-${p.id}`} className="form-input" list={`models-${p.id}`} value={model} maxLength={120}
            onChange={(e) => setModel(e.target.value)} />
          <datalist id={`models-${p.id}`}>{modelOptions.map((m) => <option key={m} value={m} />)}</datalist>
          <span className="form-hint">Pick a suggestion or type any model id your key can use. “Test” lists them.</span>
          <div className="aip-actions">
            <button className="btn btn-primary aip-sm" disabled={!canSave || !!busy || (!saved && key.trim().length < 8) || !model.trim()}
              onClick={save}><KeyRound size={14} /> {busy === 'save' ? 'Saving…' : saved ? 'Save changes' : 'Save key'}</button>
            <a className="aip-link" href={p.key_url} target="_blank" rel="noopener noreferrer">Get a key <ExternalLink size={12} /></a>
          </div>
        </div>
      )}

      {test && (
        <div className={`aip-test ${test.ok && test.model_available !== false ? 'is-ok' : 'is-bad'}`} role="status">
          {test.ok
            ? test.model_available === false
              ? <>Key works, but <code>{test.model}</code> isn’t available to it. {test.models.length} models found — pick one from the Model list.</>
              : <>Key works · {test.models.length} models available{test.model_available ? <> · <code>{test.model}</code> ✓</> : null}</>
            : <>{test.error}</>}
        </div>
      )}

      <div className="aip-card-foot">
        <button className="btn btn-secondary aip-sm" onClick={onOpen} disabled={!canSave && !saved}>
          {open ? 'Close' : saved ? 'Edit' : 'Add key'}
        </button>
        {saved && !selected && <button className="btn btn-primary aip-sm" disabled={!!busy} onClick={select}><Cpu size={14} /> Use this</button>}
        {saved && <button className="btn btn-ghost aip-sm" disabled={!!busy} onClick={doTest}>{busy === 'test' ? 'Testing…' : 'Test'}</button>}
        {saved && <button className="btn btn-ghost aip-sm aip-danger" disabled={!!busy} onClick={remove} aria-label={`Delete ${p.label} key`}><Trash2 size={14} /></button>}
        {!saved && !open && <a className="aip-link" href={p.key_url} target="_blank" rel="noopener noreferrer">Get a key <ExternalLink size={12} /></a>}
      </div>
    </article>
  );
};
