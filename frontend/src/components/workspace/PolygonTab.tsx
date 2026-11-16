import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Globe2, Link2, Plus, RefreshCw, Eye, PlayCircle, UploadCloud, GitCommit, Package, History, Unlink } from 'lucide-react';
import { Problem } from '../../types/problem';
import { Modal } from '../common/Modal';
import { ApiArtifact, problemsApi } from '../../api/client';
import {
  BuildPreflight, BuildStatus, PlanItem, polygonApi, PolygonOverview, PolygonStatus, RemoteProblem, SyncPlan, SyncRun, SyncScope,
} from '../../api/polygon';
import { CodeBlock, Field, Notice, Section, StatusBadge } from '../verification/shared';

interface PolygonTabProps {
  problem: Problem;
}

const INCLUDE = [
  { id: 'info', label: 'Settings (TL/ML, stdin/stdout)' }, { id: 'statement', label: 'Statement' },
  { id: 'tutorial', label: 'Editorial → tutorial field' }, { id: 'validator', label: 'Validator' },
  { id: 'checker', label: 'Custom checker' }, { id: 'generators', label: 'Generators' },
  { id: 'solutions', label: 'Solutions' }, { id: 'tests', label: 'Verified tests' },
];
const DEFAULT_INCLUDE = ['info', 'statement', 'validator', 'checker', 'generators', 'solutions', 'tests'];
const TAGS = ['MA', 'OK', 'WA', 'TL', 'TO', 'TM', 'ML', 'RE', 'PE', 'RJ', 'NR'];
const NON_CODE = new Set(['specification', 'statement', 'editorial', 'checker', 'validator', 'generator']);
const ACTION_STATUS: Record<string, string> = {
  create: 'queued', update: 'running', unchanged: 'passed', conflict: 'failed', blocked: 'cancelled', upload: 'pending',
};
const fmt = (s?: string | null) => (s ? new Date(s).toLocaleString() : '—');

export const PolygonTab: React.FC<PolygonTabProps> = ({ problem }) => {
  const pid = problem.id;
  const [account, setAccount] = useState<PolygonStatus | null>(null);
  const [ov, setOv] = useState<PolygonOverview | null>(null);
  const [artifacts, setArtifacts] = useState<ApiArtifact[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<SyncPlan | null>(null);
  const [dryRun, setDryRun] = useState<SyncRun | null>(null);
  const [include, setInclude] = useState<string[]>(DEFAULT_INCLUDE);
  const [solutions, setSolutions] = useState<string[] | null>(null);
  const [tags, setTags] = useState<Record<string, string>>({});
  const [allowUnverified, setAllowUnverified] = useState<string[]>([]);
  const [overwrite, setOverwrite] = useState<string[]>([]);
  const [modal, setModal] = useState<null | 'sync' | 'commit' | 'build' | 'create' | 'link'>(null);
  const [lastRun, setLastRun] = useState<SyncRun | null>(null);
  const [remoteInfo, setRemoteInfo] = useState<Record<string, any> | null>(null);

  const integ = ov?.integration;
  const linked = !!integ?.external_problem_id && !['unlinked', 'creating', 'create_unknown'].includes(integ.sync_status);
  const scope: SyncScope = useMemo(() => ({ include, solutions: solutions ?? undefined, tags, allow_unverified: allowUnverified, overwrite_remote: overwrite }),
    [include, solutions, tags, allowUnverified, overwrite]);

  const load = useCallback(async () => {
    try {
      const [a, o, arts] = await Promise.all([polygonApi.status(), polygonApi.overview(pid), problemsApi.listArtifacts(pid)]);
      setAccount(a); setOv(o); setArtifacts(arts);
    } catch (e) { setError((e as Error).message); }
  }, [pid]);
  useEffect(() => { void load(); }, [load]);

  // poll a running sync
  useEffect(() => {
    if (!lastRun || !['planned', 'running'].includes(lastRun.status)) return;
    const t = setTimeout(async () => { try { setLastRun(await polygonApi.run(pid, lastRun.id)); void load(); } catch { /* keep */ } }, 1500);
    return () => clearTimeout(t);
  }, [lastRun, pid, load]);

  const act = async <T,>(fn: () => Promise<T>, after?: (r: T) => void) => {
    setBusy(true); setError(null);
    try { const r = await fn(); after?.(r); await load(); return r; } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const solutionArtifacts = artifacts.filter((a) => !NON_CODE.has(a.artifact_type) && a.content.trim());
  const selectedSolutions = solutions ?? solutionArtifacts.filter((a) => ['reference_solution', 'brute_force'].includes(a.artifact_type)).map((a) => a.id);
  const toggle = (list: string[], v: string) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const items = (dryRun?.plan ?? plan)?.items ?? [];
  const changes = items.filter((i) => i.action === 'create' || i.action === 'update');
  const uploadedCount = (ov?.item_states ?? []).filter((s) => s.status === 'uploaded').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {error && <Notice kind="error">{error}</Notice>}

      {/* A. Account */}
      <Section title="Polygon account" icon={<Globe2 size={16} style={{ color: 'var(--brand-primary)' }} />}
        right={<button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy || !account?.configured}
          onClick={() => act(() => polygonApi.test(), (t) => setAccount(t.status))}>Test connection</button>}>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          <span>{!account ? 'Loading…' : account.configured ? `Configured (${account.source}, key ${account.key_hint})` : 'Not configured — set credentials on the Polygon Integration settings page'}</span>
          <span>Last test: {account?.last_test_ok === null || !account ? '—' : account.last_test_ok ? 'OK' : `failed (${account.last_test_kind})`} {fmt(account?.last_test_at)}</span>
          <span>Last success: {fmt(account?.last_success_at)}</span>
          <span>Last sync of this problem: {fmt(integ?.last_synced_at)}</span>
        </div>
        {account?.last_test_ok === false && account.last_test_message && <Notice kind="error">{account.last_test_message}</Notice>}
      </Section>

      {/* B. Mapping */}
      <Section title="Problem mapping" icon={<Link2 size={16} style={{ color: 'var(--brand-primary)' }} />}
        right={linked ? (
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => act(() => polygonApi.refresh(pid), setRemoteInfo)}><RefreshCw size={13} /> Refresh remote state</button>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} disabled={busy} title="Forget the link locally (nothing changes on Polygon)" onClick={() => act(() => polygonApi.unlink(pid))}><Unlink size={13} /> Unlink</button>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: 6 }}>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy || !account?.configured} onClick={() => setModal('link')}><Link2 size={13} /> Connect existing</button>
            <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={busy || !account?.configured} onClick={() => setModal('create')}><Plus size={13} /> Create new</button>
          </div>
        )}>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: 8, fontSize: 12 }}>
          <div>Local: <strong>{problem.title}</strong> ({ov ? `${ov.problem.time_limit_seconds}s / ${ov.problem.memory_limit_mb}MB` : '…'})</div>
          <div>Polygon ID: <strong>{integ?.external_problem_id ?? '—'}</strong></div>
          <div>Remote name: {integ?.remote_name ?? '—'} {integ?.remote_owner && `(owner ${integ.remote_owner}, ${integ.access_type})`}</div>
          <div>Status: <StatusBadge status={integ?.sync_status ?? 'unlinked'} /></div>
          <div>Revision: {integ?.remote_revision ?? '—'} • working copy {integ?.working_copy_revision ?? '—'}{integ?.remote_modified ? ' • uncommitted changes' : ''}</div>
          <div>Checked: {fmt(integ?.last_remote_check_at)}</div>
        </div>
        {integ?.sync_status === 'create_unknown' && (
          <Notice kind="warning">A creation request had an unknown outcome. <button className="btn btn-secondary" style={{ fontSize: 12 }} onClick={() => act(() => polygonApi.reconcileCreate(pid))}>Reconcile with Polygon</button></Notice>
        )}
        {remoteInfo && (
          <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
            Remote: TL {remoteInfo.info?.timeLimit} ms, ML {remoteInfo.info?.memoryLimit} MB • validator {remoteInfo.validator || '(none)'} • checker {remoteInfo.checker || '(none)'} •
            {' '}{remoteInfo.source_files?.length} source files • {remoteInfo.solutions?.length} solutions • statements: {remoteInfo.statement_languages?.join(', ') || 'none'}
          </div>
        )}
      </Section>

      {/* C + D. Package preview & synchronization */}
      <Section title="Package preview & synchronization" icon={<UploadCloud size={16} style={{ color: 'var(--brand-primary)' }} />}>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 12 }}>
          {INCLUDE.map((i) => (
            <label key={i.id} style={{ display: 'flex', gap: 4, alignItems: 'center' }}>
              <input type="checkbox" checked={include.includes(i.id)} onChange={() => { setInclude(toggle(include, i.id)); setDryRun(null); }} /> {i.label}
            </label>
          ))}
        </div>
        {include.includes('solutions') && solutionArtifacts.length > 0 && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4, fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>Solutions to upload (incorrect solutions only when explicitly selected):</span>
            {solutionArtifacts.map((a) => (
              <div key={a.id} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input type="checkbox" checked={selectedSolutions.includes(a.id)} onChange={() => { setSolutions(toggle(selectedSolutions, a.id)); setDryRun(null); }} />
                <span style={{ minWidth: 160 }}>{a.name || a.artifact_type} v{a.version}</span>
                <select className="form-select" style={{ width: 'auto', padding: '2px 6px', fontSize: 12 }} value={tags[a.id] ?? ''}
                  onChange={(e) => { setTags({ ...tags, [a.id]: e.target.value }); setDryRun(null); }}>
                  <option value="">tag: auto</option>{TAGS.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            ))}
          </div>
        )}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => act(() => polygonApi.preview(pid, scope), (r) => { setPlan(r); setDryRun(null); })}>
            <Eye size={13} /> Preview (local only)
          </button>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy || !linked} onClick={() => act(() => polygonApi.dryRun(pid, scope), setDryRun)}>
            <PlayCircle size={13} /> Dry run (reads Polygon, writes nothing)
          </button>
          <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={busy || !linked || !dryRun || changes.length === 0} onClick={() => setModal('sync')}>
            <UploadCloud size={13} /> Upload {changes.length} change(s) to working copy
          </button>
        </div>
        {!linked && <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>Link or create a Polygon problem to run a dry run and upload.</div>}
        {(dryRun?.plan ?? plan) && <PlanView plan={(dryRun?.plan ?? plan)!} dry={!!dryRun} allowUnverified={allowUnverified} overwrite={overwrite}
          onAllow={(k) => { setAllowUnverified(toggle(allowUnverified, k)); setDryRun(null); }}
          onOverwrite={(k) => { setOverwrite(toggle(overwrite, k)); setDryRun(null); }} />}
        {lastRun && <RunView run={lastRun} />}
      </Section>

      {/* E. Commit & build */}
      <Section title="Commit & package build" icon={<GitCommit size={16} style={{ color: 'var(--brand-primary)' }} />}>
        {linked && uploadedCount === 0 && (
          <Notice kind="warning">
            Nothing has been uploaded to this Polygon problem yet. Do these in order: <strong>Dry run</strong> → <strong>Upload</strong> (above) → <strong>Commit</strong> → <strong>Build package</strong>.
            A build of an empty problem is refused by Polygon.
          </Notice>
        )}
        {linked && uploadedCount > 0 && integ?.remote_modified && (
          <Notice>Uploaded changes are in your working copy but not committed yet. Commit before building — packages are built from committed revisions.</Notice>
        )}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={busy || !linked} onClick={() => setModal('commit')}><GitCommit size={13} /> Commit working copy…</button>
          <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy || !linked || uploadedCount === 0}
            title={uploadedCount === 0 ? 'Upload the package first (Dry run → Upload)' : undefined}
            onClick={() => setModal('build')}><Package size={13} /> Build package…</button>
          {linked && integ?.working_copy_revision != null && integ.remote_revision != null && integ.working_copy_revision < integ.remote_revision && (
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy}
              onClick={() => act(() => polygonApi.updateWorkingCopy(pid, integ.external_problem_id!))}>Update outdated working copy</button>
          )}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', display: 'flex', flexDirection: 'column', gap: 4 }}>
          <span>Last commit: {integ?.last_commit ? `${integ.last_commit.committed ? 'committed' : 'not committed'} — revision ${integ.last_commit.revision_before} → ${integ.last_commit.revision_after} (${integ.last_commit.message ?? ''}) ${integ.last_commit.at ? fmt(integ.last_commit.at) : ''}` : '—'}</span>
          <span>Last build: {integ?.last_build ? <>request {integ.last_build.request_status}, package state <StatusBadge status={integ.last_build.state} />{integ.last_build.package_id ? ` (package #${integ.last_build.package_id}, revision ${integ.last_build.package_revision})` : ''}</> : 'not started'}</span>
        </div>
        {linked && integ?.last_build && <BuildStatusView pid={pid} onUpdate={load} />}
      </Section>

      {/* F. History */}
      <Section title="Synchronization history" icon={<History size={16} style={{ color: 'var(--brand-primary)' }} />}>
        {!ov?.runs.length ? <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>No Polygon operations yet.</span> : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
            {ov.runs.map((r) => <HistoryRow key={r.id} pid={pid} run={r} />)}
          </div>
        )}
      </Section>

      {/* modals */}
      <CreateModal open={modal === 'create'} onClose={() => setModal(null)} busy={busy} defaultName={problem.slug ?? ''}
        onCreate={(name) => act(() => polygonApi.create(pid, name), () => setModal(null))} />
      <LinkModal open={modal === 'link'} onClose={() => setModal(null)} busy={busy}
        onLink={(id, name) => act(() => polygonApi.link(pid, id, name), () => setModal(null))} />
      <Modal isOpen={modal === 'sync'} onClose={() => setModal(null)} title="Upload to Polygon working copy" subtitle={`${integ?.remote_name} (#${integ?.external_problem_id})`}
        footer={<>
          <button className="btn btn-secondary" onClick={() => setModal(null)}>Cancel</button>
          <button className="btn btn-primary" disabled={busy} onClick={() => act(() => polygonApi.sync(pid, dryRun!.id, integ!.external_problem_id!), (r) => { setLastRun(r); setModal(null); setDryRun(null); })}>
            Upload {changes.length} change(s)
          </button>
        </>}>
        <div style={{ fontSize: 13, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <span>These changes from dry run <code>{dryRun?.id.slice(0, 8)}</code> will be written to your Polygon <strong>working copy</strong>. Nothing is committed.</span>
          <ul style={{ paddingLeft: 18, fontSize: 12 }}>{changes.map((c) => <li key={c.key}>{c.action} — {c.label}{c.remote_name ? ` → ${c.remote_name}` : ''}{c.remote_index ? ` → test #${c.remote_index}` : ''}</li>)}</ul>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>If local or remote state changed since the dry run, the upload is refused.</span>
        </div>
      </Modal>
      <CommitModal open={modal === 'commit'} onClose={() => setModal(null)} busy={busy} integ={integ} problemTitle={problem.title}
        onCommit={(msg, minor) => act(() => polygonApi.commit(pid, integ!.external_problem_id!, msg, minor), () => setModal(null))} />
      <BuildModal open={modal === 'build'} onClose={() => setModal(null)} pid={pid} integ={integ} busy={busy}
        onBuild={(full, verify, ack) => act(() => polygonApi.build(pid, integ!.external_problem_id!, full, verify, ack), () => setModal(null))} />
    </div>
  );
};

const PlanView: React.FC<{ plan: SyncPlan; dry: boolean; allowUnverified: string[]; overwrite: string[]; onAllow: (k: string) => void; onOverwrite: (k: string) => void }> = ({ plan, dry, allowUnverified, overwrite, onAllow, onOverwrite }) => (
  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
    <div style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
      {dry ? 'Dry run against current Polygon state' : 'Local preview (remote not checked)'} — {Object.entries(plan.counts).map(([k, v]) => `${v} ${k}`).join(', ')}
      {plan.remote_only_tests.length > 0 && ` • remote-only tests kept untouched: #${plan.remote_only_tests.join(', #')}`}
    </div>
    {plan.warnings.map((w, i) => <Notice key={i} kind="warning">{w}</Notice>)}
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead><tr style={{ textAlign: 'left', color: 'var(--text-muted)', borderBottom: '1px solid var(--border-subtle)' }}>
          <th style={{ padding: 6 }}>Item</th><th style={{ padding: 6 }}>Remote</th><th style={{ padding: 6 }}>Phase 4</th>
          <th style={{ padding: 6 }}>Sync state</th><th style={{ padding: 6 }}>Action</th><th style={{ padding: 6 }}>Reason</th>
        </tr></thead>
        <tbody>
          {plan.items.map((i: PlanItem) => (
            <tr key={i.key} style={{ borderBottom: '1px solid var(--border-subtle)', verticalAlign: 'top' }}>
              <td style={{ padding: 6 }}>{i.label}{i.local_version ? ` v${i.local_version}` : ''}</td>
              <td style={{ padding: 6, fontFamily: 'var(--font-mono)' }}>{i.remote_name ?? (i.remote_index ? `test #${i.remote_index}` : '—')}</td>
              <td style={{ padding: 6 }} title={i.verification.detail}><StatusBadge status={i.verification.status === 'verified' ? 'passed' : i.verification.status === 'failed' ? 'failed' : i.verification.status === 'n/a' ? 'n/a' : 'unchecked'} /></td>
              <td style={{ padding: 6 }}>{i.state.replace(/_/g, ' ')}</td>
              <td style={{ padding: 6 }}><StatusBadge status={ACTION_STATUS[i.action] ?? 'pending'} /> {i.action}</td>
              <td style={{ padding: 6, maxWidth: 380 }}>
                {i.reason}
                {i.action === 'blocked' && (i.type === 'solution' || i.key.startsWith('generator:')) && i.verification.status !== 'verified' && (
                  <label style={{ display: 'block', marginTop: 4 }}><input type="checkbox" checked={allowUnverified.includes(i.key)} onChange={() => onAllow(i.key)} /> upload anyway (unverified)</label>
                )}
                {(i.action === 'conflict' || overwrite.includes(i.key)) && (i.type === 'file' || i.type === 'solution') && !i.reason?.includes('older') && (
                  <label style={{ display: 'block', marginTop: 4 }}><input type="checkbox" checked={overwrite.includes(i.key)} onChange={() => onOverwrite(i.key)} /> overwrite remote file</label>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
    <details><summary style={{ fontSize: 12, color: 'var(--text-muted)', cursor: 'pointer' }}>Not synchronized by PolyPilot</summary>
      <ul style={{ fontSize: 12, paddingLeft: 18 }}>{plan.not_supported.map((n) => <li key={n}>{n}</li>)}</ul>
    </details>
  </div>
);

const RunView: React.FC<{ run: SyncRun }> = ({ run }) => (
  <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 10, display: 'flex', flexDirection: 'column', gap: 6, fontSize: 12 }}>
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}><StatusBadge status={run.status} /> {run.summary}</div>
    {(run.result?.operations ?? []).map((o: any, i: number) => (
      <div key={i} style={{ display: 'flex', gap: 8 }}><StatusBadge status={o.outcome === 'uploaded' || o.outcome === 'adopted' ? 'passed' : o.outcome === 'skipped' ? 'cancelled' : 'failed'} />
        <span style={{ fontFamily: 'var(--font-mono)' }}>{o.key}</span> <span style={{ color: 'var(--text-muted)' }}>{o.detail}</span></div>
    ))}
  </div>
);

const HistoryRow: React.FC<{ pid: string; run: SyncRun }> = ({ pid, run }) => {
  const [detail, setDetail] = useState<SyncRun | null>(null);
  return (
    <details onToggle={(e) => { if ((e.target as HTMLDetailsElement).open && !detail) polygonApi.run(pid, run.id).then(setDetail).catch(() => undefined); }}>
      <summary style={{ fontSize: 12, cursor: 'pointer', display: 'flex', gap: 8, alignItems: 'center' }}>
        <StatusBadge status={run.status} /> <strong>{run.kind}</strong> <span style={{ color: 'var(--text-muted)' }}>{fmt(run.created_at)}</span> <span>{run.summary}</span>
      </summary>
      {detail && (
        <div style={{ paddingLeft: 16, display: 'flex', flexDirection: 'column', gap: 6 }}>
          {detail.result?.operations && <RunView run={detail} />}
          {detail.operations && detail.operations.length > 0 && (
            <CodeBlock label={`API requests (${detail.operations.length}) — secrets never recorded`} maxHeight={200}
              text={detail.operations.map((o) => `${o.status.padEnd(9)} ${o.method} ${o.duration_ms ?? '?'}ms ${o.error_kind ? `[${o.error_kind}] ${o.error_message}` : o.response_summary ?? ''}`).join('\n')} />
          )}
          {detail.kind === 'commit' && detail.result && <CodeBlock label="Commit result" text={JSON.stringify(detail.result, null, 2)} />}
        </div>
      )}
    </details>
  );
};

const BuildStatusView: React.FC<{ pid: string; onUpdate: () => void }> = ({ pid, onUpdate }) => {
  const [st, setSt] = useState<BuildStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const check = () => polygonApi.buildStatus(pid).then((s) => { setSt(s); setErr(null); onUpdate(); }).catch((e) => setErr(e.message));
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <button className="btn btn-ghost" style={{ fontSize: 12, alignSelf: 'flex-start' }} onClick={check}><RefreshCw size={13} /> Check package status on Polygon</button>
      {err && <Notice kind="error">{err}</Notice>}
      {st && (
        <div style={{ fontSize: 12 }}>
          State: <StatusBadge status={st.state} /> — {st.packages.length} package(s) on Polygon
          {st.packages.slice(-3).reverse().map((p) => <div key={p.id} style={{ color: 'var(--text-muted)' }}>#{p.id} rev {p.revision} {p.type} {p.state} {p.comment} ({new Date(p.creationTimeSeconds * 1000).toLocaleString()})</div>)}
        </div>
      )}
    </div>
  );
};

const CreateModal: React.FC<{ open: boolean; onClose: () => void; busy: boolean; defaultName: string; onCreate: (n: string) => void }> = ({ open, onClose, busy, defaultName, onCreate }) => {
  const [name, setName] = useState(defaultName.toLowerCase().replace(/[^a-z0-9-]/g, '-').slice(0, 64));
  const valid = /^[a-z0-9][a-z0-9-]{0,63}$/.test(name);
  return (
    <Modal isOpen={open} onClose={onClose} title="Create a new Polygon problem" subtitle="problem.create — runs once; duplicates are checked first"
      footer={<><button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={busy || !valid} onClick={() => onCreate(name)}>Create “{name}” on Polygon</button></>}>
      <Field label="Polygon problem name" hint="Lowercase letters, digits and dashes">
        <input className="form-input" value={name} onChange={(e) => setName(e.target.value)} />
      </Field>
    </Modal>
  );
};

const LinkModal: React.FC<{ open: boolean; onClose: () => void; busy: boolean; onLink: (id: string, name: string) => void }> = ({ open, onClose, busy, onLink }) => {
  const [list, setList] = useState<RemoteProblem[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [sel, setSel] = useState<RemoteProblem | null>(null);
  const [confirm, setConfirm] = useState('');
  useEffect(() => { if (open && list === null) polygonApi.listProblems().then(setList).catch((e) => setErr(e.message)); }, [open, list]);
  return (
    <Modal isOpen={open} onClose={onClose} title="Connect an existing Polygon problem" subtitle="Only problems accessible with your API key are listed"
      footer={<><button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={busy || !sel || confirm !== sel.name} onClick={() => sel && onLink(String(sel.id), confirm)}>Link</button></>}>
      {err && <Notice kind="error">{err}</Notice>}
      {list === null && !err && <span style={{ fontSize: 12 }}>Loading problems from Polygon…</span>}
      <div style={{ maxHeight: 260, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 2 }}>
        {list?.map((p) => (
          <label key={p.id} style={{ fontSize: 12, display: 'flex', gap: 8, padding: 4, backgroundColor: sel?.id === p.id ? 'var(--bg-surface-hover)' : undefined }}>
            <input type="radio" checked={sel?.id === p.id} onChange={() => { setSel(p); setConfirm(''); }} />
            #{p.id} <strong>{p.name}</strong> owner {p.owner} • {p.accessType} • rev {p.revision}{p.modified ? ' • uncommitted changes' : ''}
          </label>
        ))}
      </div>
      {sel && <Field label={`Type the problem name “${sel.name}” to confirm`}><input className="form-input" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>}
    </Modal>
  );
};

const CommitModal: React.FC<{ open: boolean; onClose: () => void; busy: boolean; integ: any; problemTitle: string; onCommit: (m: string, minor: boolean) => void }> = ({ open, onClose, busy, integ, problemTitle, onCommit }) => {
  const [msg, setMsg] = useState(`PolyPilot: sync ${problemTitle}`);
  const [minor, setMinor] = useState(false);
  const [confirm, setConfirm] = useState('');
  return (
    <Modal isOpen={open} onClose={onClose} title="Commit Polygon working copy" subtitle="problem.commitChanges — creates a new revision"
      footer={<><button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={busy || confirm !== String(integ?.external_problem_id) || msg.trim().length < 3} onClick={() => onCommit(msg, minor)}>Commit</button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
        <span>Problem <strong>{integ?.remote_name}</strong> (#{integ?.external_problem_id}), revision {integ?.remote_revision}{integ?.remote_modified ? ' — working copy has uncommitted changes' : ' — no uncommitted changes detected at last check'}.</span>
        <Notice kind="warning">All uncommitted changes in your Polygon working copy are committed, including any made in the Polygon web UI.</Notice>
        <Field label="Commit message"><input className="form-input" value={msg} onChange={(e) => setMsg(e.target.value)} /></Field>
        <label style={{ fontSize: 12 }}><input type="checkbox" checked={minor} onChange={(e) => setMinor(e.target.checked)} /> Minor changes (no email notification)</label>
        <Field label={`Type the Polygon problem ID (${integ?.external_problem_id}) to confirm`}><input className="form-input" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
      </div>
    </Modal>
  );
};

const BuildModal: React.FC<{ open: boolean; onClose: () => void; pid: string; integ: any; busy: boolean; onBuild: (full: boolean, verify: boolean, ack: boolean) => void }> = ({ open, onClose, pid, integ, busy, onBuild }) => {
  const [pf, setPf] = useState<BuildPreflight | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [full, setFull] = useState(false);
  const [verify, setVerify] = useState(true);
  const [ack, setAck] = useState(false);
  const [confirm, setConfirm] = useState('');
  useEffect(() => { if (open) { setPf(null); setErr(null); setAck(false); polygonApi.preflight(pid).then(setPf).catch((e) => setErr(e.message)); } }, [open, pid]);
  return (
    <Modal isOpen={open} onClose={onClose} title="Build Polygon package" subtitle="problem.buildPackage — builds from the committed revision"
      footer={<><button className="btn btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={busy || !pf || (pf.issues.length > 0 && !ack) || confirm !== String(integ?.external_problem_id)} onClick={() => onBuild(full, verify, ack)}>Request build</button></>}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
        <span>Problem <strong>{integ?.remote_name}</strong> (#{integ?.external_problem_id})</span>
        {err && <Notice kind="error">{err}</Notice>}
        {!pf && !err && <span style={{ fontSize: 12 }}>Running preflight checks against Polygon…</span>}
        {pf && (pf.ready ? <Notice>Preflight: no issues reported.</Notice> : (
          <Notice kind="warning"><strong>Preflight issues:</strong><ul style={{ paddingLeft: 18 }}>{pf.issues.map((i) => <li key={i}>{i}</li>)}</ul></Notice>
        ))}
        {pf && pf.issues.length > 0 && <label style={{ fontSize: 12 }}><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I reviewed these issues and still want to request a build</label>}
        <label style={{ fontSize: 12 }}><input type="checkbox" checked={full} onChange={(e) => setFull(e.target.checked)} /> Full build (standard + linux + windows)</label>
        <label style={{ fontSize: 12 }}><input type="checkbox" checked={verify} onChange={(e) => setVerify(e.target.checked)} /> Verify (run all solutions on all tests)</label>
        <Field label={`Type the Polygon problem ID (${integ?.external_problem_id}) to confirm`}><input className="form-input" value={confirm} onChange={(e) => setConfirm(e.target.value)} /></Field>
        <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>An accepted request is not a successful build — check the package status afterwards.</span>
      </div>
    </Modal>
  );
};
