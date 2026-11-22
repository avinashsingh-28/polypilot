import React, { useEffect, useState } from 'react';
import { ArrowRight, Bot, ChevronRight, Cpu, FolderGit2, Globe2, Loader2, Plus, Server, ShieldCheck, Sparkles } from 'lucide-react';
import { Problem } from '../types/problem';
import { Badge } from '../components/common/Badge';
import { apiClient } from '../api/client';
import { polygonApi, PolygonStatus } from '../api/polygon';
import { useAuth } from '../auth/AuthContext';

interface DashboardPageProps {
  problems: Problem[];
  onNavigateNewProblem: () => void;
  onOpenProblem: (id: string) => void;
}

type Level = 'ok' | 'warn' | 'error' | 'loading';
interface Check { label: string; detail: string; level: Level; icon: React.ReactNode }

const LEVEL_COLOR: Record<Level, string> = {
  ok: 'var(--success-text)', warn: 'var(--warning-text)', error: 'var(--danger-text)', loading: 'var(--text-muted)',
};

function timeAgo(iso?: string): string {
  if (!iso) return '—';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return `${Math.floor(s / 86400)} d ago`;
}

/** Live system status from the backend (nothing here is simulated). */
function useSystemStatus() {
  const [worker, setWorker] = useState<{ ok: boolean; sandbox: boolean; busy: number; queued: number } | null>(null);
  const [ai, setAi] = useState<{ configured: boolean; model: string; label?: string; source?: string | null; calls_last_24h: number; daily_limit: number } | null>(null);
  const [polygon, setPolygon] = useState<PolygonStatus | null>(null);
  const [db, setDb] = useState<boolean | null>(null);
  useEffect(() => {
    const base = (import.meta.env.VITE_API_URL ?? '/api/v1').replace(/\/api\/v1$/, '');
    fetch(`${base}/health/ready`).then((r) => setDb(r.ok)).catch(() => setDb(false));
    fetch(`${base}/health/worker`).then(async (r) => {
      const d = await r.json();
      setWorker({ ok: r.ok && d.workers_alive > 0, sandbox: !!d.sandbox_available, busy: d.workers_busy ?? 0, queued: d.queued_runs ?? 0 });
    }).catch(() => setWorker({ ok: false, sandbox: false, busy: 0, queued: 0 }));
    apiClient<{ configured: boolean; model: string; label?: string; source?: string | null; calls_last_24h: number; daily_limit: number }>('/ai/status').then(setAi).catch(() => setAi(null));
    polygonApi.status().then(setPolygon).catch(() => setPolygon(null));
  }, []);
  return { worker, ai, polygon, db };
}

const Metric: React.FC<{ label: string; value: React.ReactNode; hint: string; icon: React.ReactNode; tint: string }> = ({ label, value, hint, icon, tint }) => (
  <div className="card" style={{ padding: '18px 20px', display: 'flex', gap: 14, alignItems: 'flex-start' }}>
    <div style={{ width: 38, height: 38, borderRadius: 'var(--radius-md)', display: 'grid', placeItems: 'center', flexShrink: 0,
      background: `color-mix(in srgb, ${tint} 12%, transparent)`, color: tint }}>{icon}</div>
    <div style={{ minWidth: 0 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-secondary)' }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.25, marginTop: 2, letterSpacing: '-0.02em' }}>{value}</div>
      <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{hint}</div>
    </div>
  </div>
);

export const DashboardPage: React.FC<DashboardPageProps> = ({ problems, onNavigateNewProblem, onOpenProblem }) => {
  const { user } = useAuth();
  const { worker, ai, polygon, db } = useSystemStatus();
  const generated = problems.filter((p) => p.status === 'generated').length;
  const generating = problems.filter((p) => p.status === 'generating').length;
  const latest = [...problems].sort((a, b) => (b.updatedAt ?? '').localeCompare(a.updatedAt ?? ''))[0];
  const name = user?.email.split('@')[0] ?? '';

  const checks: Check[] = [
    { label: 'Server & database', icon: <Server size={15} />,
      level: db === null ? 'loading' : db ? 'ok' : 'error', detail: db === null ? 'Checking…' : db ? 'Connected' : 'Database unreachable' },
    { label: 'Verification worker', icon: <Cpu size={15} />,
      level: !worker ? 'loading' : !worker.ok ? 'error' : !worker.sandbox ? 'warn' : 'ok',
      detail: !worker ? 'Checking…' : !worker.ok ? 'Offline — start python -m app.worker' : !worker.sandbox ? 'Online, but the Docker sandbox is unavailable'
        : worker.busy ? `Running a job · ${worker.queued} queued` : 'Online · sandbox ready' },
    { label: 'AI provider', icon: <Bot size={15} />,
      level: !ai ? 'loading' : ai.configured ? 'ok' : 'warn',
      detail: !ai ? 'Checking…' : !ai.configured ? 'No API key yet — add one on the AI Providers page'
        : ai.source === 'own' ? `${ai.label ?? ''} · ${ai.model} · your key · ${ai.calls_last_24h} calls today`
        : `${ai.model} · ${ai.calls_last_24h}/${ai.daily_limit} calls today` },
    { label: 'Codeforces Polygon', icon: <Globe2 size={15} />,
      level: !polygon ? 'loading' : !polygon.configured ? 'warn' : polygon.last_test_ok === false ? 'error' : polygon.last_success_at ? 'ok' : 'warn',
      detail: !polygon ? 'Checking…' : !polygon.configured ? 'Not connected — add keys under Polygon Integration'
        : polygon.last_test_ok === false ? `Last connection test failed (${polygon.last_test_kind})`
        : polygon.last_success_at ? `Connected · ${polygon.accessible_problems ?? '?'} problems accessible` : 'Credentials saved · run a connection test' },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Hero */}
      <div className="card" style={{ padding: '28px 30px', position: 'relative', overflow: 'hidden', border: 'none',
        background: 'var(--brand-gradient)', color: '#fff', boxShadow: 'var(--shadow-brand)' }}>
        <div aria-hidden style={{ position: 'absolute', right: -80, top: -120, width: 360, height: 360, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,255,255,0.28), transparent 65%)' }} />
        <div style={{ position: 'relative', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 20, flexWrap: 'wrap' }}>
          <div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 600, padding: '3px 10px',
              borderRadius: 'var(--radius-full)', background: 'rgba(255,255,255,0.16)', marginBottom: 10 }}>
              <Sparkles size={13} /> PolyPilot workspace
            </div>
            <h1 style={{ fontSize: 24, fontWeight: 700 }}>Welcome back{name ? `, ${name}` : ''}</h1>
            <p style={{ fontSize: 14, opacity: 0.9, marginTop: 6, maxWidth: 620 }}>
              Turn a problem idea into a verified Codeforces Polygon package — AI drafting, sandboxed verification and Polygon sync in one place.
            </p>
          </div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            {latest && (
              <button onClick={() => onOpenProblem(latest.id)} className="btn"
                style={{ background: 'rgba(255,255,255,0.14)', color: '#fff', border: '1px solid rgba(255,255,255,0.3)' }}>
                Continue “{latest.title.length > 22 ? latest.title.slice(0, 21) + '…' : latest.title}” <ArrowRight size={14} />
              </button>
            )}
            <button onClick={onNavigateNewProblem} className="btn" style={{ background: '#fff', color: 'var(--brand-primary)', fontWeight: 650, boxShadow: '0 6px 16px -6px rgba(0,0,0,0.3)' }}>
              <Plus size={16} /> Create problem
            </button>
          </div>
        </div>
      </div>

      {/* Metrics (computed from your real problems and the live worker) */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 16 }}>
        <Metric label="Problems" value={problems.length} hint={problems.length ? 'In your workspace' : 'None yet'}
          icon={<FolderGit2 size={18} />} tint="var(--brand-primary)" />
        <Metric label="AI-generated" value={generated} hint="All artifacts drafted" icon={<Sparkles size={18} />} tint="var(--brand-accent)" />
        <Metric label="Generating now" value={generating} hint={generating ? 'AI pipeline running' : 'Nothing in progress'}
          icon={generating ? <Loader2 size={18} style={{ animation: 'spin 1s linear infinite' }} /> : <Bot size={18} />} tint="var(--info-text)" />
        <Metric label="Verification queue" value={worker ? worker.queued + worker.busy : '—'}
          hint={!worker ? 'Checking…' : worker.ok ? (worker.busy ? 'Worker busy' : 'Worker idle') : 'Worker offline'}
          icon={<ShieldCheck size={18} />} tint="var(--success-text)" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(420px, 1fr))', gap: 24, alignItems: 'start' }}>
        {/* Recent problems */}
        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <h2 style={{ fontSize: 15, fontWeight: 650, color: 'var(--text-primary)' }}>Recent problems</h2>
            {problems.length > 0 && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{problems.length} total</span>}
          </div>
          {problems.length === 0 ? (
            <div style={{ padding: '52px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12 }}>
              <div style={{ width: 48, height: 48, borderRadius: 'var(--radius-lg)', background: 'var(--brand-gradient-soft)', display: 'grid', placeItems: 'center', color: 'var(--brand-primary)' }}>
                <FolderGit2 size={22} />
              </div>
              <div>
                <h3 style={{ fontSize: 15, fontWeight: 650, color: 'var(--text-primary)' }}>No problems yet</h3>
                <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4, maxWidth: 340 }}>
                  Describe an idea in a sentence — PolyPilot drafts the statement, solutions, validator and generator for you to verify.
                </p>
              </div>
              <button onClick={onNavigateNewProblem} className="btn btn-primary" style={{ marginTop: 4 }}><Plus size={14} /> Create your first problem</button>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
                <thead>
                  <tr style={{ color: 'var(--text-muted)', fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--border-subtle)' }}>
                    <th style={{ padding: '10px 20px', fontWeight: 600 }}>Problem</th>
                    <th style={{ padding: '10px 12px', fontWeight: 600 }}>Difficulty</th>
                    <th style={{ padding: '10px 12px', fontWeight: 600 }}>Status</th>
                    <th style={{ padding: '10px 12px', fontWeight: 600 }}>Updated</th>
                    <th style={{ padding: '10px 20px' }} />
                  </tr>
                </thead>
                <tbody>
                  {problems.slice(0, 8).map((p) => (
                    <tr key={p.id} onClick={() => onOpenProblem(p.id)} className="dash-row"
                      style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer' }}>
                      <td style={{ padding: '13px 20px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{p.title}</div>
                        <div style={{ fontSize: 11.5, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{p.slug}</div>
                      </td>
                      <td style={{ padding: '13px 12px' }}><Badge difficulty={p.difficulty} size="sm" /></td>
                      <td style={{ padding: '13px 12px' }}><Badge status={p.status} size="sm" /></td>
                      <td style={{ padding: '13px 12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>{timeAgo(p.updatedAt)}</td>
                      <td style={{ padding: '13px 20px', textAlign: 'right' }}>
                        <button onClick={(e) => { e.stopPropagation(); onOpenProblem(p.id); }} className="btn btn-secondary" style={{ minHeight: 28, padding: '4px 10px', fontSize: 12 }}>
                          Open <ChevronRight size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Live system status */}
          <div className="card" style={{ padding: '18px 20px' }}>
            <h2 style={{ fontSize: 15, fontWeight: 650, color: 'var(--text-primary)', marginBottom: 12 }}>System status</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {checks.map((c) => (
                <div key={c.label} style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
                  <div style={{ width: 30, height: 30, borderRadius: 'var(--radius-sm)', display: 'grid', placeItems: 'center', flexShrink: 0,
                    background: 'var(--bg-surface-subtle)', color: 'var(--text-secondary)' }}>{c.icon}</div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{c.label}</div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={c.detail}>{c.detail}</div>
                  </div>
                  <span aria-label={c.level} style={{ width: 9, height: 9, borderRadius: '50%', flexShrink: 0, background: LEVEL_COLOR[c.level],
                    boxShadow: c.level === 'ok' ? '0 0 0 4px color-mix(in srgb, var(--success-text) 18%, transparent)' : 'none' }} />
                </div>
              ))}
            </div>
          </div>

          {/* Workflow guide */}
          <div className="card" style={{ padding: '18px 20px' }}>
            <h2 style={{ fontSize: 15, fontWeight: 650, color: 'var(--text-primary)', marginBottom: 12 }}>How it works</h2>
            <ol style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
              {[
                ['Draft', 'Create a problem and let the AI draft every artifact.'],
                ['Verify', 'In Verification, run the numbered steps: samples → validator → tests → reference → differential.'],
                ['Publish', 'In the Polygon tab: dry run → upload → commit → build.'],
              ].map(([t, d], i) => (
                <li key={t} style={{ display: 'flex', gap: 12 }}>
                  <span style={{ width: 24, height: 24, borderRadius: '50%', flexShrink: 0, display: 'grid', placeItems: 'center', fontSize: 12, fontWeight: 700,
                    background: 'var(--brand-primary-subtle)', color: 'var(--brand-primary)' }}>{i + 1}</span>
                  <span style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}><strong style={{ color: 'var(--text-primary)' }}>{t}.</strong> {d}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
};
