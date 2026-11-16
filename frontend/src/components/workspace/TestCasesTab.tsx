import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Layers, Plus, Upload, Download, Cpu, ShieldCheck, Trash2, Eye, RefreshCw, FileInput } from 'lucide-react';
import { Problem } from '../../types/problem';
import { Modal } from '../common/Modal';
import { ApiRun, ApiTestCase, ApiTestCaseDetail, verificationApi } from '../../api/verification';
import { CodeBlock, Field, Notice, RunStatusCard, Section, StatusBadge } from '../verification/shared';

interface TestCasesTabProps {
  problem: Problem;
}

const MAX_UPLOAD = 2 * 1024 * 1024;

export const TestCasesTab: React.FC<TestCasesTabProps> = ({ problem }) => {
  const pid = problem.id;
  const [tests, setTests] = useState<ApiTestCase[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState<ApiTestCaseDetail | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [manual, setManual] = useState({ input: '', expected: '', invalid: false });
  const [gen, setGen] = useState({ count: 10, seed: 1, gen_type: 'small', extra_args: '' });
  const [run, setRun] = useState<ApiRun | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      setTests(await verificationApi.listTests(pid));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [pid]);

  useEffect(() => { void load(); }, [load]);

  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); await load(); } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  };

  const addManual = () => act(async () => {
    await verificationApi.createTest(pid, {
      input_data: manual.input,
      expected_output: manual.expected || undefined,
      test_type: manual.invalid ? 'invalid' : 'manual',
    });
    setManual({ input: '', expected: '', invalid: false });
    setShowAdd(false);
  });

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = '';
    if (!f) return;
    if (f.size > MAX_UPLOAD) { setError(`File too large (max ${MAX_UPLOAD / 1024 / 1024} MB)`); return; }
    void act(async () => {
      const text = await f.text();
      await verificationApi.createTest(pid, { input_data: text, test_type: 'upload', filename: f.name });
    });
  };

  const startRun = (type: 'generate' | 'validator', config: Record<string, unknown> = {}) =>
    act(async () => setRun(await verificationApi.startRun(pid, type, config)));

  const view = (t: ApiTestCase) => act(async () => setSelected(await verificationApi.getTest(pid, t.id)));

  const counts = (tests ?? []).reduce<Record<string, number>>((m, t) => ({ ...m, [t.validation_status]: (m[t.validation_status] ?? 0) + 1 }), {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Section
        title={`Test Suite (${tests?.length ?? '…'} cases)`}
        icon={<Layers size={16} style={{ color: 'var(--brand-primary)' }} />}
        right={
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy}
              onClick={() => act(async () => { const r = await verificationApi.importSamples(pid); if (!r.length) setError('No new samples to import'); })}>
              <FileInput size={13} /> Import samples
            </button>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => setShowAdd(true)}>
              <Plus size={13} /> Manual test
            </button>
            <button className="btn btn-secondary" style={{ fontSize: 12 }} disabled={busy} onClick={() => fileRef.current?.click()}>
              <Upload size={13} /> Upload file
            </button>
            <input ref={fileRef} type="file" accept=".txt,.in,text/plain" hidden onChange={onUpload} />
            <button className="btn btn-primary" style={{ fontSize: 12 }} disabled={busy || !tests?.length} onClick={() => startRun('validator')}>
              <ShieldCheck size={13} /> Run validator
            </button>
            <button className="btn btn-ghost" style={{ fontSize: 12 }} onClick={() => void load()} title="Refresh"><RefreshCw size={13} /></button>
          </div>
        }
      >
        <div style={{ display: 'flex', gap: 12, fontSize: 12, color: 'var(--text-secondary)', flexWrap: 'wrap' }}>
          {['valid', 'invalid', 'unchecked', 'error'].map((s) => (
            <span key={s} style={{ display: 'flex', gap: 4, alignItems: 'center' }}><StatusBadge status={s} /> {counts[s] ?? 0}</span>
          ))}
          <span style={{ color: 'var(--text-muted)' }}>Inputs are marked valid only after the sandboxed testlib validator accepts them.</span>
        </div>
        {error && <Notice kind="error">{error}</Notice>}
      </Section>

      <Section title="Generate tests with the testlib generator" icon={<Cpu size={16} style={{ color: 'var(--brand-primary)' }} />}>
        <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
          <Field label="Count"><input className="form-input" type="number" min={1} max={200} value={gen.count} onChange={(e) => setGen({ ...gen, count: +e.target.value })} /></Field>
          <Field label="Base seed"><input className="form-input" type="number" min={0} value={gen.seed} onChange={(e) => setGen({ ...gen, seed: +e.target.value })} /></Field>
          <Field label="Type (argv[1])">
            <select className="form-select" value={gen.gen_type} onChange={(e) => setGen({ ...gen, gen_type: e.target.value })}>
              <option value="small">small (random)</option><option value="large">large (max size)</option><option value="edge">edge (boundary)</option>
            </select>
          </Field>
          <Field label="Extra args" hint="argv[3…], space separated"><input className="form-input" value={gen.extra_args} onChange={(e) => setGen({ ...gen, extra_args: e.target.value })} /></Field>
          <button className="btn btn-primary" style={{ fontSize: 12, marginBottom: 4 }} disabled={busy}
            onClick={() => startRun('generate', { count: gen.count, seed: gen.seed, gen_type: gen.gen_type, extra_args: gen.extra_args.trim() ? gen.extra_args.trim().split(/\s+/) : [] })}>
            <Cpu size={13} /> Generate
          </button>
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
          Runs <code>gen &lt;type&gt; &lt;seed+i&gt; [args]</code> in the sandbox, validates every output, and saves only accepted, non-duplicate inputs (seed recorded for reproduction).
        </div>
        <RunStatusCard problemId={pid} run={run} onChange={(d) => { if (d.status !== 'running' && d.status !== 'queued') void load(); }}>
          {(d) => (
            <>
              {d.report?.generator && (
                <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {d.report.generator.invalid?.map((x: any) => (
                    <Notice key={`i${x.seed}`} kind="warning">Seed {x.seed}: validator rejected generator output — {x.diagnostics || 'no diagnostics'}</Notice>
                  ))}
                  {d.report.generator.failures?.map((x: any) => (
                    <Notice key={`f${x.seed}`} kind="error">Seed {x.seed}: {x.error} {x.stderr}</Notice>
                  ))}
                </div>
              )}
              {d.report?.validator && (
                <div style={{ fontSize: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                  {d.report.validator.cases.map((c: any, i: number) => (
                    <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'baseline' }}>
                      <StatusBadge status={c.correct ? 'passed' : 'failed'} />
                      <span>{c.label}</span>
                      <span style={{ color: 'var(--text-muted)' }}>expected {c.expected}, validator {c.verdict}{c.diagnostics ? ` — ${c.diagnostics.slice(0, 160)}` : ''}</span>
                    </div>
                  ))}
                  <span style={{ color: 'var(--text-muted)' }}>{d.report.validator.note}</span>
                </div>
              )}
            </>
          )}
        </RunStatusCard>
      </Section>

      <div className="card" style={{ overflowX: 'auto' }}>
        {tests === null ? (
          <div style={{ padding: 30, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Loading test cases…</div>
        ) : tests.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-muted)' }}>
            <Layers size={32} style={{ margin: '0 auto 12px auto' }} />
            <h3 style={{ fontSize: 15, color: 'var(--text-primary)', fontWeight: 600 }}>No test cases yet</h3>
            <p style={{ fontSize: 13, marginTop: 4 }}>Import samples from the specification, add a manual test, upload a file, or run the generator.</p>
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: 13 }}>
            <thead>
              <tr style={{ backgroundColor: 'var(--bg-surface-subtle)', borderBottom: '1px solid var(--border-subtle)', color: 'var(--text-secondary)', fontSize: 11, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                <th style={{ padding: '10px 16px' }}>#</th><th style={{ padding: '10px 16px' }}>Type</th>
                <th style={{ padding: '10px 16px' }}>Source</th><th style={{ padding: '10px 16px' }}>Input preview</th>
                <th style={{ padding: '10px 16px' }}>Validator</th><th style={{ padding: '10px 16px', textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t, i) => (
                <tr key={t.id} style={{ borderBottom: '1px solid var(--border-subtle)' }}>
                  <td style={{ padding: '10px 16px', color: 'var(--text-muted)', fontWeight: 600 }}>{i + 1}</td>
                  <td style={{ padding: '10px 16px' }}><StatusBadge status={t.test_type.toUpperCase()} />{t.has_expected_output && <span style={{ fontSize: 11, color: 'var(--text-muted)' }}> +answer</span>}</td>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
                    {t.generator_cmd ?? t.generation_meta?.filename ?? (t.generation_meta?.source === 'specification' ? 'statement sample' : 'manual')}
                  </td>
                  <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 12, maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {t.input_preview.slice(0, 80).replace(/\n/g, ' ⏎ ')} <span style={{ color: 'var(--text-muted)' }}>({t.input_bytes} B)</span>
                  </td>
                  <td style={{ padding: '10px 16px' }} title={t.validation_feedback ?? ''}><StatusBadge status={t.validation_status} /></td>
                  <td style={{ padding: '10px 16px', textAlign: 'right', whiteSpace: 'nowrap' }}>
                    <button className="btn btn-ghost" style={{ padding: 4 }} title="Inspect" onClick={() => view(t)}><Eye size={14} /></button>
                    <button className="btn btn-ghost" style={{ padding: 4 }} title="Delete" disabled={busy} onClick={() => act(() => verificationApi.deleteTest(pid, t.id))}><Trash2 size={14} /></button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal isOpen={showAdd} onClose={() => setShowAdd(false)} title="Add manual test case" subtitle="Stored in PostgreSQL; validated when you run the validator"
        footer={<>
          <button className="btn btn-secondary" onClick={() => setShowAdd(false)}>Cancel</button>
          <button className="btn btn-primary" disabled={busy || !manual.input.trim()} onClick={addManual}><Plus size={13} /> Add</button>
        </>}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <Field label="Input"><textarea className="form-textarea" rows={8} style={{ fontFamily: 'var(--font-mono)' }} value={manual.input} onChange={(e) => setManual({ ...manual, input: e.target.value })} /></Field>
          <Field label="Expected output (optional)"><textarea className="form-textarea" rows={4} style={{ fontFamily: 'var(--font-mono)' }} value={manual.expected} onChange={(e) => setManual({ ...manual, expected: e.target.value })} /></Field>
          <label style={{ fontSize: 13, display: 'flex', gap: 6, alignItems: 'center' }}>
            <input type="checkbox" checked={manual.invalid} onChange={(e) => setManual({ ...manual, invalid: e.target.checked })} />
            This input is intentionally <strong>invalid</strong> (the validator must reject it)
          </label>
        </div>
      </Modal>

      <Modal isOpen={!!selected} onClose={() => setSelected(null)} title="Test case" subtitle={selected ? `${selected.test_type} • ${selected.input_bytes} bytes • ${selected.validation_status}` : ''}
        footer={<button className="btn btn-secondary" onClick={() => setSelected(null)}>Close</button>}>
        {selected && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <CodeBlock label="Input" text={selected.input_data} filename={`test-${selected.id.slice(0, 8)}.in`} maxHeight={300} />
            {selected.expected_output !== null && <CodeBlock label="Expected output" text={selected.expected_output} filename={`test-${selected.id.slice(0, 8)}.ans`} />}
            {selected.validation_feedback && <Notice>{selected.validation_feedback}</Notice>}
            {selected.generation_meta && <CodeBlock label="Metadata" text={JSON.stringify(selected.generation_meta, null, 2)} />}
            <button className="btn btn-ghost" style={{ alignSelf: 'flex-start', fontSize: 12 }}
              onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([selected.input_data])); a.download = `test-${selected.id.slice(0, 8)}.in`; a.click(); }}>
              <Download size={13} /> Download input
            </button>
          </div>
        )}
      </Modal>
    </div>
  );
};
