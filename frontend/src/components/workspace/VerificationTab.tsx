import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Activity, Bug, CheckCircle2, Code2, GitCompare, Play, RefreshCw, Server, ShieldCheck, Sparkles, Zap } from 'lucide-react';
import { Problem } from '../../types/problem';
import { ApiArtifact, problemsApi } from '../../api/client';
import {
  ApiCounterexample, ApiRepair, ApiRun, ApiRunDetail, ApiSandboxStatus, ApiVerificationSummary, RunType, SourceSpec,
  isActive, verificationApi,
} from '../../api/verification';
import { CodeBlock, ExecTable, Field, Notice, RunStatusCard, Section, StatusBadge } from '../verification/shared';

interface VerificationTabProps {
  problem: Problem;
}

type View = 'dashboard' | 'solutions' | 'differential' | 'stress' | 'counterexamples';
const NON_CODE = new Set(['specification', 'statement', 'editorial']);

export const VerificationTab: React.FC<VerificationTabProps> = ({ problem }) => {
  const pid = problem.id;
  const [view, setView] = useState<View>('dashboard');
  const [summary, setSummary] = useState<ApiVerificationSummary | null>(null);
  const [sandbox, setSandbox] = useState<ApiSandboxStatus | null>(null);
  const [artifacts, setArtifacts] = useState<ApiArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const [s, a] = await Promise.all([verificationApi.summary(pid), problemsApi.listArtifacts(pid)]);
      setSummary(s); setArtifacts(a); setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [pid]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { verificationApi.sandboxStatus().then(setSandbox).catch(() => setSandbox(null)); }, []);
  useEffect(() => {
    if (!summary?.active_runs.length) return;
    const t = setTimeout(() => void refresh(), 2500);
    return () => clearTimeout(t);
  }, [summary, refresh]);

  const codeArtifacts = useMemo(() => artifacts.filter((a) => !NON_CODE.has(a.artifact_type) && a.content.trim()), [artifacts]);

  const views: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <Activity size={13} /> },
    { id: 'solutions', label: 'Solution testing', icon: <Code2 size={13} /> },
    { id: 'differential', label: 'Differential', icon: <GitCompare size={13} /> },
    { id: 'stress', label: 'Stress', icon: <Zap size={13} /> },
    { id: 'counterexamples', label: `Counterexamples${summary ? ` (${summary.counterexample_count})` : ''}`, icon: <Bug size={13} /> },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {views.map((v) => (
          <button key={v.id} onClick={() => setView(v.id)} className={`btn ${view === v.id ? 'btn-primary' : 'btn-secondary'}`} style={{ fontSize: 12 }}>
            {v.icon}{v.label}
          </button>
        ))}
        <button className="btn btn-ghost" style={{ marginLeft: 'auto' }} title="Refresh" onClick={() => void refresh()}><RefreshCw size={14} /></button>
      </div>
      {sandbox && !sandbox.available && (
        <Notice kind="error">
          Sandbox unavailable (mode: {sandbox.mode}, image present: {String(sandbox.image_present)}). No code will be executed.
          Install Docker (WSL2 + Docker Engine or Docker Desktop) and build the image: <code>docker build -t {sandbox.image} backend/sandbox</code>
        </Notice>
      )}
      {error && <Notice kind="error">{error}</Notice>}
      {view === 'dashboard' && <Dashboard pid={pid} summary={summary} sandbox={sandbox} onStarted={refresh} />}
      {view === 'solutions' && <SolutionTesting pid={pid} artifacts={codeArtifacts} summary={summary} />}
      {view === 'differential' && <Comparison pid={pid} mode="differential" artifacts={codeArtifacts} summary={summary} onFound={() => setView('counterexamples')} />}
      {view === 'stress' && <Comparison pid={pid} mode="stress" artifacts={codeArtifacts} summary={summary} onFound={() => setView('counterexamples')} />}
      {view === 'counterexamples' && <Counterexamples pid={pid} aiConfigured={!!summary?.ai_configured} artifacts={codeArtifacts} />}
    </div>
  );
};

// ─── Dashboard ───────────────────────────────────────────────────────────────
const STAGES: { type: RunType; label: string }[] = [
  { type: 'compile', label: 'Compilation' }, { type: 'validator', label: 'Validator' },
  { type: 'generate', label: 'Generator' }, { type: 'reference', label: 'Reference solution' },
  { type: 'differential', label: 'Differential testing' }, { type: 'stress', label: 'Stress testing' },
  { type: 'candidate', label: 'Candidate / WA-TLE tests' },
];

const Dashboard: React.FC<{ pid: string; summary: ApiVerificationSummary | null; sandbox: ApiSandboxStatus | null; onStarted: () => void }> = ({ pid, summary, sandbox, onStarted }) => {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  if (!summary) return <div className="card" style={{ padding: 30, textAlign: 'center', color: 'var(--text-muted)' }}>Loading verification status…</div>;
  const latest = Object.values(summary.latest_by_type).filter(Boolean) as ApiRun[];
  const newest = latest.sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const core = (['validator', 'reference', 'differential'] as RunType[]).map((t) => summary.latest_by_type[t]?.status);
  const overall = core.every((s) => s === 'passed') ? 'passed' : core.some((s) => s === 'failed') ? 'failed' : core.some((s) => s) ? 'incomplete' : 'not run';

  const start = async (type: RunType, cfg: Record<string, unknown> = {}) => {
    setBusy(true); setErr(null);
    try { await verificationApi.startRun(pid, type, cfg); onStarted(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div className="card" style={{ padding: '16px 20px', display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap',
        borderLeft: `4px solid ${overall === 'passed' ? 'var(--success-text)' : overall === 'failed' ? 'var(--danger-text)' : 'var(--border-subtle)'}` }}>
        <ShieldCheck size={26} style={{ color: overall === 'passed' ? 'var(--success-text)' : 'var(--text-muted)' }} />
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Overall: {overall.toUpperCase()}</div>
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Based on the latest validator, reference and differential runs. Passing tests are evidence, not a proof of correctness.
          </div>
          {newest && <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>Latest run: {newest.test_type} — {newest.summary}</div>}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
          <Server size={14} /> Sandbox: {sandbox ? (sandbox.available ? `Docker ${sandbox.server_version} (${sandbox.mode})` : 'unavailable') : 'checking…'}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: 12 }}>
        {STAGES.map(({ type, label }) => {
          const r = summary.latest_by_type[type];
          return (
            <div key={type} className="card" style={{ padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span><StatusBadge status={r?.status} />
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', minHeight: 32 }}>{r?.summary ?? 'No run yet'}</div>
              {r?.completed_at && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{new Date(r.completed_at).toLocaleString()}</div>}
            </div>
          );
        })}
      </div>

      <Section title="Quick actions" icon={<Play size={15} style={{ color: 'var(--brand-primary)' }} />}>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => start('validator')}>Test validator (valid + invalid inputs)</button>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => start('reference')}>Run reference on all tests</button>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => start('differential', { iterations: 100 })}>Differential (100 iterations)</button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Test cases: {summary.test_case_counts.total ?? 0} total • {summary.test_case_counts.valid ?? 0} valid • {summary.test_case_counts.invalid ?? 0} invalid • {summary.test_case_counts.unchecked ?? 0} unchecked
        </div>
        {err && <Notice kind="error">{err}</Notice>}
      </Section>

      {summary.active_runs.length > 0 && (
        <Section title={`Active runs (${summary.active_runs.length})`} icon={<Activity size={15} />}>
          {summary.active_runs.map((r) => <RunStatusCard key={r.id} problemId={pid} run={r} />)}
        </Section>
      )}
    </div>
  );
};

// ─── Source picker ───────────────────────────────────────────────────────────
const SourcePicker: React.FC<{ label: string; artifacts: ApiArtifact[]; value: SourceSpec; onChange: (s: SourceSpec) => void; allowInline?: boolean }> = ({ label, artifacts, value, onChange, allowInline = true }) => {
  const inline = value.source !== undefined;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: '1 1 260px' }}>
      <Field label={label}>
        <select className="form-select" value={inline ? '__inline' : value.artifact_id ?? (value.artifact_type ? `type:${value.artifact_type}` : '')}
          onChange={(e) => {
            const v = e.target.value;
            if (v === '__inline') onChange({ source: '', language: 'cpp', label: 'pasted source' });
            else if (v.startsWith('type:')) onChange({ artifact_type: v.slice(5) });
            else onChange({ artifact_id: v });
          }}>
          <option value="">— select —</option>
          {artifacts.map((a) => <option key={a.id} value={a.id}>{a.name || a.artifact_type} (v{a.version}, {a.language || 'cpp'})</option>)}
          {allowInline && <option value="__inline">Paste source code…</option>}
        </select>
      </Field>
      {inline && (
        <>
          <select className="form-select" value={value.language} onChange={(e) => onChange({ ...value, language: e.target.value })}>
            <option value="cpp">C++17</option><option value="python">Python 3</option>
          </select>
          <textarea className="form-textarea" rows={8} style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }} value={value.source}
            onChange={(e) => onChange({ ...value, source: e.target.value })} placeholder="Paste solution source" />
        </>
      )}
    </div>
  );
};

const specReady = (s: SourceSpec) => !!(s.artifact_id || s.artifact_type || (s.source && s.source.trim()));

function useStarter(pid: string, initial: ApiRun | null | undefined) {
  const [run, setRun] = useState<ApiRun | null>(initial ?? null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (!run && initial) setRun(initial); }, [initial, run]);
  const start = async (type: RunType, cfg: Record<string, unknown>) => {
    setBusy(true); setErr(null);
    try { setRun(await verificationApi.startRun(pid, type, cfg)); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return { run, busy, err, start };
}

// ─── Solution testing ────────────────────────────────────────────────────────
const SolutionTesting: React.FC<{ pid: string; artifacts: ApiArtifact[]; summary: ApiVerificationSummary | null }> = ({ pid, artifacts, summary }) => {
  const [spec, setSpec] = useState<SourceSpec>({});
  const [expected, setExpected] = useState('');
  const [tl, setTl] = useState<string>('');
  const [saveOutputs, setSaveOutputs] = useState(false);
  const s = useStarter(pid, summary?.latest_by_type.candidate);
  const ref = useStarter(pid, summary?.latest_by_type.reference);
  const limits = tl ? { time_limit_sec: +tl } : {};

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Section title="Reference solution" icon={<CheckCircle2 size={15} style={{ color: 'var(--brand-primary)' }} />}
        right={<button className="btn btn-primary" style={{ fontSize: 12 }} disabled={ref.busy} onClick={() => ref.start('reference', { save_outputs: saveOutputs, ...limits })}><Play size={13} /> Run on all tests</button>}>
        <label style={{ fontSize: 12, display: 'flex', gap: 6, alignItems: 'center' }}>
          <input type="checkbox" checked={saveOutputs} onChange={(e) => setSaveOutputs(e.target.checked)} />
          Store reference outputs as expected answers for tests that have none (reference = candidate oracle, not proof)
        </label>
        {ref.err && <Notice kind="error">{ref.err}</Notice>}
        <RunStatusCard problemId={pid} run={ref.run}>
          {(d) => d.report?.reference && (<><ExecTable rows={d.report.reference.results} /><span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.report.reference.note}</span></>)}
        </RunStatusCard>
      </Section>

      <Section title="Test a solution / WA-TLE candidate" icon={<Code2 size={15} style={{ color: 'var(--brand-primary)' }} />}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
          <SourcePicker label="Solution" artifacts={artifacts} value={spec} onChange={setSpec} />
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: '1 1 200px' }}>
            <Field label="Expected verdict" hint="Leave empty to expect AC on every test">
              <select className="form-select" value={expected} onChange={(e) => setExpected(e.target.value)}>
                <option value="">(none)</option><option value="AC">AC</option><option value="WA">WA</option><option value="TLE">TLE</option>
                <option value="RE">RE</option><option value="MLE">MLE</option>
              </select>
            </Field>
            <Field label="Time limit (s)" hint="Default: problem limit; capped by server"><input className="form-input" type="number" step="0.1" value={tl} onChange={(e) => setTl(e.target.value)} /></Field>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={!specReady(spec) || s.busy} onClick={() => s.start('compile', { target: spec })}>Compile only</button>
          <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={!specReady(spec) || s.busy}
            onClick={() => s.start('candidate', { candidate: spec, expected_verdict: expected || undefined, ...limits })}><Play size={13} /> Run on all tests</button>
        </div>
        {s.err && <Notice kind="error">{s.err}</Notice>}
        <RunStatusCard problemId={pid} run={s.run}>
          {(d) => d.report?.candidate && (
            <>
              <div style={{ fontSize: 13 }}>Verdict: <StatusBadge status={d.report.candidate.verdict} />{d.report.candidate.expected_verdict && <> (expected {d.report.candidate.expected_verdict})</>}</div>
              {d.report.candidate.verdict === 'TLE?' && <Notice kind="warning">Timeout was not reproduced consistently or looked like an idle/overloaded wall-clock timeout — inconclusive.</Notice>}
              <ExecTable rows={d.report.candidate.results} />
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{d.report.candidate.note}</span>
            </>
          )}
        </RunStatusCard>
      </Section>
    </div>
  );
};

// ─── Differential / stress ───────────────────────────────────────────────────
const Comparison: React.FC<{ pid: string; mode: 'differential' | 'stress'; artifacts: ApiArtifact[]; summary: ApiVerificationSummary | null; onFound: () => void }> = ({ pid, mode, artifacts, summary, onFound }) => {
  const byType = (t: string) => artifacts.find((a) => a.artifact_type === t);
  const [ref, setRef] = useState<SourceSpec>(() => byType('reference_solution') ? { artifact_id: byType('reference_solution')!.id } : {});
  const [cand, setCand] = useState<SourceSpec>(() => mode === 'differential' && byType('brute_force') ? { artifact_id: byType('brute_force')!.id } : {});
  const [cfg, setCfg] = useState({ iterations: 100, seed: 1, time_limit_sec: '', max_seconds: 300, gen_type: 'small', stop_on_first: true, minimize: true });
  const s = useStarter(pid, summary?.latest_by_type[mode]);
  const hasBrute = !!byType('brute_force')?.content.trim();

  return (
    <Section title={mode === 'differential' ? 'Differential testing: reference vs brute force' : 'Stress testing: reference vs candidate'}
      icon={mode === 'differential' ? <GitCompare size={15} style={{ color: 'var(--brand-primary)' }} /> : <Zap size={15} style={{ color: 'var(--brand-primary)' }} />}>
      {mode === 'differential' && !hasBrute && (
        <Notice kind="warning">Differential testing is disabled: this problem has no brute-force solution artifact. Generate one (Phase 3) or paste a slow-but-obviously-correct solution below.</Notice>
      )}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <SourcePicker label="Reference solution" artifacts={artifacts} value={ref} onChange={setRef} />
        <SourcePicker label={mode === 'differential' ? 'Brute-force solution' : 'Candidate solution'} artifacts={artifacts} value={cand} onChange={setCand} />
      </div>
      <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
        <Field label="Iterations" hint="Server max applies"><input className="form-input" type="number" min={1} value={cfg.iterations} onChange={(e) => setCfg({ ...cfg, iterations: +e.target.value })} /></Field>
        <Field label="Base seed"><input className="form-input" type="number" min={0} value={cfg.seed} onChange={(e) => setCfg({ ...cfg, seed: +e.target.value })} /></Field>
        <Field label="Per-run time limit (s)"><input className="form-input" type="number" step="0.1" placeholder="problem" value={cfg.time_limit_sec} onChange={(e) => setCfg({ ...cfg, time_limit_sec: e.target.value })} /></Field>
        <Field label="Overall budget (s)"><input className="form-input" type="number" min={10} value={cfg.max_seconds} onChange={(e) => setCfg({ ...cfg, max_seconds: +e.target.value })} /></Field>
        <Field label="Generator type">
          <select className="form-select" value={cfg.gen_type} onChange={(e) => setCfg({ ...cfg, gen_type: e.target.value })}>
            <option value="small">small</option><option value="edge">edge</option><option value="large">large</option>
          </select>
        </Field>
      </div>
      <div style={{ display: 'flex', gap: 16, fontSize: 12, flexWrap: 'wrap' }}>
        <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" checked={cfg.stop_on_first} onChange={(e) => setCfg({ ...cfg, stop_on_first: e.target.checked })} /> Stop at first counterexample</label>
        <label style={{ display: 'flex', gap: 6 }}><input type="checkbox" checked={cfg.minimize} onChange={(e) => setCfg({ ...cfg, minimize: e.target.checked })} /> Minimize counterexample</label>
      </div>
      <button className="btn btn-primary" style={{ fontSize: 12, alignSelf: 'flex-start' }}
        disabled={s.busy || !specReady(ref) || !specReady(cand) || isActive(s.run)}
        onClick={() => s.start(mode, { reference: ref, candidate: cand, iterations: cfg.iterations, seed: cfg.seed, max_seconds: cfg.max_seconds,
          gen_type: cfg.gen_type, stop_on_first: cfg.stop_on_first, minimize: cfg.minimize, ...(cfg.time_limit_sec ? { time_limit_sec: +cfg.time_limit_sec } : {}) })}>
        <Play size={13} /> Start {mode}
      </button>
      {s.err && <Notice kind="error">{s.err}</Notice>}
      <RunStatusCard problemId={pid} run={s.run}>
        {(d: ApiRunDetail) => {
          const c = d.report?.comparison;
          if (!c) return null;
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
              <div>Completed {c.iterations_completed}/{c.iterations_requested} iterations • seeds {c.seed}…{c.seed + c.iterations_completed - 1} • {c.checker}{c.stop_reason ? ` • stopped: ${c.stop_reason}` : ''}</div>
              {Object.entries(c.failure_kinds ?? {}).map(([k, sd]) => <Notice key={k} kind="error">{k.replace(/_/g, ' ')} at seed {String(sd)}</Notice>)}
              {d.report?.rejected_inputs?.map((x: any) => <CodeBlock key={x.seed} label={`Rejected input (seed ${x.seed}) — ${x.diagnostics}`} text={x.input_preview} />)}
              {c.counterexample_ids?.length > 0 && <button className="btn btn-secondary" style={{ fontSize: 12, alignSelf: 'flex-start' }} onClick={onFound}><Bug size={13} /> Inspect counterexample(s)</button>}
              <span style={{ color: 'var(--text-muted)' }}>{c.note}</span>
            </div>
          );
        }}
      </RunStatusCard>
    </Section>
  );
};

// ─── Counterexamples & AI repair ─────────────────────────────────────────────
function lineDiff(a: string, b: string): { t: ' ' | '-' | '+'; s: string }[] {
  const A = a.split('\n'), B = b.split('\n');
  if (A.length * B.length > 400_000) return [...A.map((s) => ({ t: '-' as const, s })), ...B.map((s) => ({ t: '+' as const, s }))];
  const L = Array.from({ length: A.length + 1 }, () => new Int32Array(B.length + 1));
  for (let i = A.length - 1; i >= 0; i--) for (let j = B.length - 1; j >= 0; j--)
    L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  const out: { t: ' ' | '-' | '+'; s: string }[] = [];
  let i = 0, j = 0;
  while (i < A.length && j < B.length) {
    if (A[i] === B[j]) { out.push({ t: ' ', s: A[i] }); i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) out.push({ t: '-', s: A[i++] });
    else out.push({ t: '+', s: B[j++] });
  }
  while (i < A.length) out.push({ t: '-', s: A[i++] });
  while (j < B.length) out.push({ t: '+', s: B[j++] });
  return out;
}

const KIND_LABEL: Record<string, string> = {
  mismatch: 'Output disagreement', candidate_failure: 'Candidate failure', reference_failure: 'Reference failure', brute_failure: 'Brute-force failure',
};

const Counterexamples: React.FC<{ pid: string; aiConfigured: boolean; artifacts: ApiArtifact[] }> = ({ pid, aiConfigured, artifacts }) => {
  const [cxs, setCxs] = useState<ApiCounterexample[] | null>(null);
  const [repairs, setRepairs] = useState<ApiRepair[]>([]);
  const [sel, setSel] = useState<string | null>(null);
  const [artifactId, setArtifactId] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [c, r] = await Promise.all([verificationApi.listCounterexamples(pid), verificationApi.listRepairs(pid)]);
      setCxs(c); setRepairs(r);
      setSel((s) => s ?? c[0]?.id ?? null);
    } catch (e) { setErr((e as Error).message); }
  }, [pid]);
  useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setErr(null);
    try { await fn(); await load(); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };

  if (cxs === null) return <div className="card" style={{ padding: 30, textAlign: 'center', color: 'var(--text-muted)' }}>Loading counterexamples…</div>;
  if (!cxs.length) return (
    <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
      <Bug size={30} style={{ margin: '0 auto 10px auto' }} />
      <h3 style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 600 }}>No counterexamples</h3>
      <p style={{ fontSize: 13 }}>Failing inputs found by differential, stress, or candidate testing appear here.</p>
    </div>
  );
  const cx = cxs.find((c) => c.id === sel) ?? cxs[0];
  const cxRepairs = repairs.filter((r) => r.counterexample_id === cx.id);
  const min = cx.details?.minimization;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'minmax(200px, 260px) 1fr', gap: 16, alignItems: 'start' }}>
      <div className="card" style={{ display: 'flex', flexDirection: 'column', maxHeight: 600, overflow: 'auto' }}>
        {cxs.map((c) => (
          <button key={c.id} onClick={() => setSel(c.id)} className="btn"
            style={{ justifyContent: 'flex-start', flexDirection: 'column', alignItems: 'flex-start', gap: 2, padding: '10px 12px', borderRadius: 0,
              borderBottom: '1px solid var(--border-subtle)', backgroundColor: c.id === cx.id ? 'var(--bg-surface-hover)' : 'transparent' }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{KIND_LABEL[c.kind] ?? c.kind}</span>
            <span style={{ fontSize: 11, color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>{c.id.slice(0, 8)}{c.seed !== null ? ` • seed ${c.seed}` : ''}</span>
          </button>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
        <Section title={KIND_LABEL[cx.kind] ?? cx.kind} icon={<Bug size={15} style={{ color: 'var(--danger-text)' }} />}
          right={<span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{new Date(cx.created_at).toLocaleString()}{cx.details?.gen_cmd ? ` • ${cx.details.gen_cmd}` : ''}</span>}>
          {cx.details?.message && <Notice kind="error">{cx.details.message}</Notice>}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <CodeBlock label="Failing input" text={cx.input_data} filename={`counterexample-${cx.id.slice(0, 8)}.in`} />
            {cx.minimized_input && <CodeBlock label="Minimized input (validated, reproduces)" text={cx.minimized_input} filename={`counterexample-${cx.id.slice(0, 8)}-min.in`} />}
          </div>
          {min && <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Minimization: {min.reductions} reductions in {min.attempts} attempts ({min.original_bytes} → {min.minimized_bytes} bytes){!min.changed && ' — original kept'}</div>}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <CodeBlock label="Reference output" text={cx.ref_output} />
            <CodeBlock label="Candidate output" text={cx.candidate_output} />
          </div>
          {(cx.details?.candidate?.stderr || cx.details?.reference?.stderr) && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {cx.details?.reference?.stderr && <CodeBlock label="Reference stderr" text={cx.details.reference.stderr} />}
              {cx.details?.candidate?.stderr && <CodeBlock label="Candidate stderr" text={cx.details.candidate.stderr} />}
            </div>
          )}
        </Section>

        <Section title="AI-assisted repair" icon={<Sparkles size={15} style={{ color: 'var(--brand-primary)' }} />}>
          {!aiConfigured ? (
            <Notice kind="warning">No AI provider configured (GEMINI_API_KEY). Diagnostics and the counterexample above remain available.</Notice>
          ) : (
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end', flexWrap: 'wrap' }}>
              <Field label="Failing source" hint="Default: the candidate used by the run">
                <select className="form-select" value={artifactId} onChange={(e) => setArtifactId(e.target.value)}>
                  <option value="">(from run)</option>
                  {artifacts.map((a) => <option key={a.id} value={a.id}>{a.artifact_type} v{a.version}</option>)}
                </select>
              </Field>
              <button className="btn btn-primary" style={{ fontSize: 12, marginBottom: 4 }} disabled={busy}
                onClick={() => act(() => verificationApi.proposeRepair(pid, cx.id, artifactId || undefined))}>
                <Sparkles size={13} /> {busy ? 'Asking AI…' : 'Propose repair (1 AI call)'}
              </button>
            </div>
          )}
          {err && <Notice kind="error">{err}</Notice>}
          {cxRepairs.map((r) => <RepairCard key={r.id} pid={pid} repair={r} busy={busy} act={act} />)}
        </Section>
      </div>
    </div>
  );
};

const RepairCard: React.FC<{ pid: string; repair: ApiRepair; busy: boolean; act: (fn: () => Promise<unknown>) => Promise<void> }> = ({ pid, repair, busy, act }) => {
  const diff = useMemo(() => lineDiff(repair.original_code, repair.repaired_code), [repair]);
  const retest = repair.retest_run_id ? ({ id: repair.retest_run_id } as ApiRun) : null;
  return (
    <div style={{ border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: 12, display: 'flex', flexDirection: 'column', gap: 8 }}>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <strong style={{ fontSize: 13 }}>Repair v{repair.version}</strong>
        <StatusBadge status={repair.status === 'proposed' ? 'pending' : repair.status === 'accepted' ? 'queued' : 'cancelled'} />
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{repair.status} • {repair.language}</span>
      </div>
      {repair.suspected_bug && <div style={{ fontSize: 13 }}><strong>Suspected bug:</strong> {repair.suspected_bug}</div>}
      {repair.explanation && <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{repair.explanation}</div>}
      <Notice kind="info">Proposed by AI — unverified until it passes the re-test. Accepting never overwrites the original artifact.</Notice>
      <pre style={{ margin: 0, fontSize: 12, fontFamily: 'var(--font-mono)', maxHeight: 320, overflow: 'auto', backgroundColor: 'var(--bg-surface-subtle)', padding: 8, borderRadius: 'var(--radius-sm)' }}>
        {diff.map((l, i) => (
          <div key={i} style={{ backgroundColor: l.t === '+' ? 'var(--success-bg)' : l.t === '-' ? 'var(--danger-bg)' : undefined, color: l.t === ' ' ? 'var(--text-secondary)' : 'var(--text-primary)' }}>
            {l.t} {l.s}
          </div>
        ))}
      </pre>
      {repair.status === 'proposed' && (
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={busy} onClick={() => act(() => verificationApi.acceptRepair(pid, repair.id))}>Accept &amp; re-test</button>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => act(() => verificationApi.rejectRepair(pid, repair.id))}>Reject</button>
        </div>
      )}
      {retest && (
        <RunStatusCard problemId={pid} run={retest}>
          {(d) => d.report?.candidate && (
            <>
              <div style={{ fontSize: 12 }}>Re-test on failing input + regression suite: verdict <StatusBadge status={d.report.candidate.verdict} /></div>
              <ExecTable rows={d.report.candidate.results} />
            </>
          )}
        </RunStatusCard>
      )}
    </div>
  );
};
