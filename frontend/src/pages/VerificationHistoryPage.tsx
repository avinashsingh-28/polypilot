import React, { useCallback, useEffect, useState } from 'react';
import { ChevronRight, History, RefreshCw } from 'lucide-react';
import { Problem } from '../types/problem';
import { apiClient } from '../api/client';
import { StatusBadge } from '../components/verification/shared';

interface VerificationHistoryPageProps {
  problems: Problem[];
  onOpenProblem: (id: string) => void;
}

interface HistoryRun {
  id: string;
  problem_id: string;
  problem_title: string;
  test_type: string;
  status: string;
  summary: string | null;
  created_at: string;
  completed_at: string | null;
}

const TYPE_LABEL: Record<string, string> = {
  compile: 'Compile', validator: 'Validator', generate: 'Generate tests', reference: 'Reference',
  differential: 'Differential', stress: 'Stress', candidate: 'Candidate',
};
const TYPES = ['', 'validator', 'generate', 'reference', 'differential', 'stress', 'candidate', 'compile'];

export const VerificationHistoryPage: React.FC<VerificationHistoryPageProps> = ({ onOpenProblem }) => {
  const [runs, setRuns] = useState<HistoryRun[] | null>(null);
  const [total, setTotal] = useState(0);
  const [type, setType] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const r = await apiClient<{ total: number; items: HistoryRun[] }>(`/verification-runs?limit=100${type ? `&test_type=${type}` : ''}`);
      setRuns(r.items); setTotal(r.total); setError(null);
    } catch (e) { setError((e as Error).message); }
  }, [type]);
  useEffect(() => { void load(); }, [load]);

  const passed = runs?.filter((r) => r.status === 'passed').length ?? 0;
  const failed = runs?.filter((r) => r.status === 'failed').length ?? 0;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)' }}>Verification history</h1>
          <p style={{ fontSize: 13, color: 'var(--text-secondary)', marginTop: 4 }}>
            Every sandboxed run across your problems — validator checks, test generation, reference, differential and stress testing.
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select className="form-select" style={{ width: 'auto' }} value={type} onChange={(e) => setType(e.target.value)} aria-label="Filter by run type">
            {TYPES.map((t) => <option key={t} value={t}>{t ? TYPE_LABEL[t] : 'All run types'}</option>)}
          </select>
          <button className="btn btn-secondary" onClick={() => void load()} title="Refresh"><RefreshCw size={14} /></button>
        </div>
      </div>

      {runs && runs.length > 0 && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13, color: 'var(--text-secondary)' }}>
          <span><strong style={{ color: 'var(--text-primary)' }}>{total}</strong> runs</span>
          <span>·</span><span style={{ color: 'var(--success-text)' }}>{passed} passed</span>
          <span>·</span><span style={{ color: 'var(--danger-text)' }}>{failed} failed</span>
          {total > runs.length && <span>· showing latest {runs.length}</span>}
        </div>
      )}

      {error && <div className="card" style={{ padding: 16, color: 'var(--danger-text)', fontSize: 13 }}>{error}</div>}

      <div className="card" style={{ overflow: 'hidden' }}>
        {runs === null ? (
          <div role="status" style={{ padding: 32, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>Loading history…</div>
        ) : runs.length === 0 ? (
          <div style={{ padding: '52px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 48, height: 48, borderRadius: 'var(--radius-lg)', background: 'var(--brand-gradient-soft)', display: 'grid', placeItems: 'center', color: 'var(--brand-primary)' }}>
              <History size={22} />
            </div>
            <h3 style={{ fontSize: 15, fontWeight: 650 }}>No verification runs yet</h3>
            <p style={{ fontSize: 13, color: 'var(--text-secondary)', maxWidth: 380 }}>
              Open a problem and use the Verification tab to run the validator, generate tests and compare solutions.
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13, textAlign: 'left' }}>
              <thead>
                <tr style={{ color: 'var(--text-muted)', fontSize: 11.5, textTransform: 'uppercase', letterSpacing: '0.05em', borderBottom: '1px solid var(--border-subtle)' }}>
                  <th style={{ padding: '10px 20px', fontWeight: 600 }}>Problem</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Run</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Result</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>Summary</th>
                  <th style={{ padding: '10px 12px', fontWeight: 600 }}>When</th>
                  <th style={{ padding: '10px 20px' }} />
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr key={r.id} className="dash-row" style={{ borderBottom: '1px solid var(--border-subtle)', cursor: 'pointer', verticalAlign: 'top' }}
                    onClick={() => onOpenProblem(r.problem_id)}>
                    <td style={{ padding: '12px 20px', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap' }}>{r.problem_title}</td>
                    <td style={{ padding: '12px', whiteSpace: 'nowrap' }}>{TYPE_LABEL[r.test_type] ?? r.test_type}</td>
                    <td style={{ padding: '12px' }}><StatusBadge status={r.status} /></td>
                    <td style={{ padding: '12px', color: 'var(--text-secondary)', maxWidth: 460 }}>{r.summary}</td>
                    <td style={{ padding: '12px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{new Date(r.created_at).toLocaleString()}</td>
                    <td style={{ padding: '12px 20px', textAlign: 'right' }}><ChevronRight size={15} style={{ color: 'var(--text-muted)' }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
