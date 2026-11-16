import React, { useEffect, useState } from 'react';
import { Copy, Download, Loader2, StopCircle } from 'lucide-react';
import { Badge } from '../common/Badge';
import { ApiRun, ApiRunDetail, isActive, verificationApi } from '../../api/verification';

const STATUS_VARIANT: Record<string, 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info'> = {
  pending: 'default', queued: 'info', running: 'warning', passed: 'success', failed: 'danger', cancelled: 'default',
  Accepted: 'success', Executed: 'info', 'Wrong Answer': 'danger', 'Time Limit Exceeded': 'warning',
  'Memory Limit Exceeded': 'warning', 'Runtime Error': 'danger', 'Output Limit Exceeded': 'warning',
  'Compilation Error': 'danger', 'Internal Error': 'danger', Skipped: 'default',
  valid: 'success', invalid: 'danger', unchecked: 'default', error: 'warning',
  success: 'success', compilation_error: 'danger', internal_error: 'danger',
};

export const StatusBadge: React.FC<{ status?: string | null }> = ({ status }) =>
  status ? <Badge variant={STATUS_VARIANT[status] ?? 'default'} size="sm">{status}</Badge> : <Badge size="sm">NOT RUN</Badge>;

export const Section: React.FC<{ title: string; icon?: React.ReactNode; right?: React.ReactNode; children: React.ReactNode }> = ({ title, icon, right, children }) => (
  <div className="card" style={{ padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 12 }}>
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8, flexWrap: 'wrap' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600, fontSize: 14, color: 'var(--text-primary)' }}>
        {icon}{title}
      </div>
      {right}
    </div>
    {children}
  </div>
);

export const Notice: React.FC<{ kind?: 'error' | 'info' | 'warning'; children: React.ReactNode }> = ({ kind = 'info', children }) => {
  const c = kind === 'error' ? 'danger' : kind;
  return (
    <div style={{ padding: '10px 12px', borderRadius: 'var(--radius-sm)', fontSize: 12, lineHeight: 1.5,
      backgroundColor: `var(--${c}-bg)`, color: `var(--${c}-text)`, border: `1px solid var(--${c}-border)` }}>
      {children}
    </div>
  );
};

export function copyText(text: string) {
  void navigator.clipboard?.writeText(text);
}

export function downloadText(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/plain' }));
  const a = document.createElement('a');
  a.href = url; a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export const CodeBlock: React.FC<{ label?: string; text: string; filename?: string; maxHeight?: number }> = ({ label, text, filename, maxHeight = 220 }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 4, minWidth: 0, flex: 1 }}>
    {(label || filename) && (
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
        <span>{label}</span>
        <span style={{ display: 'flex', gap: 4 }}>
          <button className="btn btn-ghost" style={{ padding: 2 }} title="Copy" onClick={() => copyText(text)}><Copy size={12} /></button>
          {filename && <button className="btn btn-ghost" style={{ padding: 2 }} title="Download" onClick={() => downloadText(filename, text)}><Download size={12} /></button>}
        </span>
      </div>
    )}
    <pre style={{ margin: 0, padding: '8px 10px', fontSize: 12, fontFamily: 'var(--font-mono)', maxHeight, overflow: 'auto',
      backgroundColor: 'var(--bg-surface-subtle)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)',
      whiteSpace: 'pre-wrap', wordBreak: 'break-all', color: 'var(--text-primary)' }}>
      {text === '' ? <span style={{ color: 'var(--text-muted)' }}>(empty)</span> : text}
    </pre>
  </div>
);

export const Field: React.FC<{ label: string; hint?: string; children: React.ReactNode }> = ({ label, hint, children }) => (
  <div className="form-group" style={{ minWidth: 120, flex: '1 1 140px' }}>
    <label className="form-label">{label}</label>
    {children}
    {hint && <span className="form-hint">{hint}</span>}
  </div>
);

/** Polls a run while active and renders progress + summary + cancel. */
export const RunStatusCard: React.FC<{ problemId: string; run: ApiRun | null; onChange?: (r: ApiRunDetail) => void; children?: (r: ApiRunDetail) => React.ReactNode }> = ({ problemId, run, onChange, children }) => {
  const [detail, setDetail] = useState<ApiRunDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!run) { setDetail(null); return; }
    let stop = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const d = await verificationApi.getRun(problemId, run.id);
        if (stop) return;
        setDetail(d); setErr(null); onChange?.(d);
        if (isActive(d)) timer = setTimeout(tick, 1500);
      } catch (e) {
        if (!stop) { setErr((e as Error).message); timer = setTimeout(tick, 4000); }
      }
    };
    void tick();
    return () => { stop = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [problemId, run?.id]);

  if (!run) return null;
  const d = detail ?? (run as ApiRunDetail);
  const pr = d.progress ?? {};
  const pct = pr.iterations_total ? Math.min(100, Math.round(100 * (pr.iterations_done ?? 0) / pr.iterations_total)) : null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, borderTop: '1px solid var(--border-subtle)', paddingTop: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', fontSize: 13 }}>
        {isActive(d) && <Loader2 size={14} className="spin" style={{ animation: 'spin 1s linear infinite' }} />}
        <StatusBadge status={d.status} />
        <span style={{ color: 'var(--text-secondary)' }}>{d.summary}</span>
        {isActive(d) && (
          <button className="btn btn-secondary" style={{ marginLeft: 'auto', fontSize: 12 }} disabled={d.cancel_requested}
            onClick={() => verificationApi.cancelRun(problemId, d.id).then(() => undefined).catch((e) => setErr(e.message))}>
            <StopCircle size={13} /> {d.cancel_requested ? 'Stopping…' : 'Stop'}
          </button>
        )}
      </div>
      {pct !== null && (
        <div>
          <div style={{ height: 6, borderRadius: 3, backgroundColor: 'var(--bg-surface-subtle)', overflow: 'hidden' }}>
            <div style={{ width: `${pct}%`, height: '100%', backgroundColor: 'var(--brand-primary)', transition: 'width .3s' }} />
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontFamily: 'var(--font-mono)' }}>
            {pr.iterations_done ?? 0}/{pr.iterations_total} iterations
            {pr.current_seed !== undefined && pr.current_seed !== null ? ` • seed ${pr.current_seed}` : ''}
            {pr.counterexamples ? ` • ${pr.counterexamples} counterexample(s)` : ''}
            {pr.minimization_attempts ? ` • minimizing (${pr.minimization_attempts} attempts)` : ''}
          </div>
        </div>
      )}
      {d.status === 'queued' && <Notice>Waiting for the verification worker. Make sure <code>python -m app.worker</code> is running.</Notice>}
      {d.error_message && <Notice kind="error">{d.error_message}</Notice>}
      {err && <Notice kind="error">{err}</Notice>}
      {detail?.report?.compilations && <Compilations data={detail.report.compilations} />}
      {detail && !isActive(detail) && children?.(detail)}
      {detail?.logs && (
        <details>
          <summary style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer' }}>Worker log</summary>
          <CodeBlock text={detail.logs} />
        </details>
      )}
    </div>
  );
};

export const Compilations: React.FC<{ data: Record<string, any> }> = ({ data }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
    {Object.entries(data).map(([role, c]) => (
      <details key={role} open={c.status !== 'success'}>
        <summary style={{ fontSize: 12, cursor: 'pointer', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontWeight: 600 }}>{role}</span> <StatusBadge status={c.status} />
          <span style={{ color: 'var(--text-muted)' }}>{c.label} • {c.version} • {c.duration_ms} ms{c.cached ? ' (cached)' : ''}</span>
        </summary>
        {(c.stderr || c.error) && <CodeBlock text={[c.error, c.stderr].filter(Boolean).join('\n')} />}
      </details>
    ))}
  </div>
);

export const ExecTable: React.FC<{ rows: any[] }> = ({ rows }) => (
  <div style={{ overflowX: 'auto' }}>
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
      <thead>
        <tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
          <th style={{ padding: 6 }}>Test</th><th style={{ padding: 6 }}>Verdict</th><th style={{ padding: 6 }}>CPU</th>
          <th style={{ padding: 6 }}>Wall</th><th style={{ padding: 6 }}>Peak mem</th><th style={{ padding: 6 }}>Details</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderBottom: '1px solid var(--border-subtle)', verticalAlign: 'top' }}>
            <td style={{ padding: 6, fontFamily: 'var(--font-mono)' }}>{String(r.test_case_id).slice(0, 8)} <span style={{ color: 'var(--text-muted)' }}>{r.test_type}</span></td>
            <td style={{ padding: 6 }}><StatusBadge status={r.status} />{r.tle_confirmed === false && <span style={{ fontSize: 11, color: 'var(--warning-text)' }}> unconfirmed</span>}</td>
            <td style={{ padding: 6 }}>{r.time_ms} / {r.time_limit_ms} ms</td>
            <td style={{ padding: 6 }}>{r.wall_ms} ms</td>
            <td style={{ padding: 6 }}>{Math.round((r.peak_memory_kb ?? 0) / 1024)} MB</td>
            <td style={{ padding: 6, maxWidth: 360 }}>
              {r.error_details && <div>{r.error_details}</div>}
              {!r.has_expected && r.status === 'Executed' && <div style={{ color: 'var(--text-muted)' }}>No expected answer — not judged</div>}
              {(r.stdout || r.stderr) && (
                <details><summary style={{ cursor: 'pointer', color: 'var(--text-muted)' }}>output</summary>
                  <CodeBlock label="stdout" text={r.stdout ?? ''} maxHeight={120} />
                  {r.stderr && <CodeBlock label="stderr" text={r.stderr} maxHeight={120} />}
                </details>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);
