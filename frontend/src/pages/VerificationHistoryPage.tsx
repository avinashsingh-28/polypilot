import React from 'react';
import { CheckCircle2, XCircle, Clock, Cpu, ShieldCheck, History } from 'lucide-react';
import { Problem } from '../types/problem';
import { Badge } from '../components/common/Badge';

interface VerificationHistoryPageProps {
  problems: Problem[];
  onOpenProblem: (id: string) => void;
}

export const VerificationHistoryPage: React.FC<VerificationHistoryPageProps> = ({
  problems,
  onOpenProblem
}) => {
  const verifiedProblems = problems.filter((p) => p.verification && p.verification.status !== 'not_run');

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
          Verification History
        </h1>
        <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '2px' }}>
          Audit trail of deterministic C++17 compilation runs, differential stress tests, and counterexample diagnostics.
        </p>
      </div>

      {verifiedProblems.length === 0 ? (
        <div
          className="card"
          style={{
            padding: '60px 24px',
            textAlign: 'center',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            gap: '12px'
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--bg-surface-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)'
            }}
          >
            <History size={24} />
          </div>
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
              No verification runs recorded
            </h3>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px', maxWidth: '380px' }}>
              Verification runs will be automatically cataloged here as differential stress testing executes in Phase 4.
            </p>
          </div>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {verifiedProblems.map((problem) => {
            const v = problem.verification!;
            return (
              <div
                key={problem.id}
                className="card"
                style={{
                  padding: '20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '16px',
                  borderLeft: `4px solid ${v.status === 'passed' ? 'var(--success-text)' : 'var(--danger-text)'}`
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <h3 style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
                      {problem.title}
                    </h3>
                    <Badge variant={v.status === 'passed' ? 'success' : 'danger'}>
                      {v.status.toUpperCase()}
                    </Badge>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                      {v.lastRunTimestamp ? new Date(v.lastRunTimestamp).toLocaleString() : 'Recent'}
                    </span>
                  </div>

                  <button
                    onClick={() => onOpenProblem(problem.id)}
                    className="btn btn-secondary"
                    style={{ fontSize: '12px' }}
                  >
                    <span>Inspect in Workspace</span>
                  </button>
                </div>

                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                    gap: '12px',
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-surface-subtle)'
                  }}
                >
                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>DIFFERENTIAL TESTS</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                      {v.stressTestsPassed} / {v.stressTestsRun} Passed
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>SAMPLES VALIDATED</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
                      {v.samplesPassed} / {v.totalSamples} Passed
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>MAX RUNTIME</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={13} style={{ color: 'var(--brand-primary)' }} />
                      <span>{v.executionMetrics.maxTimeMs} ms</span>
                    </div>
                  </div>

                  <div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>PEAK MEMORY</div>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Cpu size={13} style={{ color: 'var(--brand-primary)' }} />
                      <span>{v.executionMetrics.maxMemoryMb} MB</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
