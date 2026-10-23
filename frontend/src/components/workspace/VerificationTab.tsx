import React, { useState } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  AlertTriangle, 
  Play, 
  Clock, 
  Cpu, 
  ShieldCheck, 
  FileCheck,
  RefreshCw
} from 'lucide-react';
import { Problem, VerificationReport } from '../../types/problem';
import { Badge } from '../common/Badge';

interface VerificationTabProps {
  problem: Problem;
}

export const VerificationTab: React.FC<VerificationTabProps> = ({ problem }) => {
  const verification = problem.verification;

  if (!verification || verification.status === 'not_run') {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <ShieldCheck size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>Verification Not Executed</h3>
        <p style={{ fontSize: '13px', marginTop: '4px', maxWidth: '440px', margin: '4px auto 16px auto' }}>
          Deterministic C++ compilation, testlib validation, differential stress testing against brute-force, and WA/TLE candidate profiling will be performed by the local worker in <strong>Phase 4</strong>.
        </p>
        <button className="btn btn-secondary" disabled title="Phase 4 execution worker">
          <Play size={14} />
          <span>Run Verification Suite (Phase 4)</span>
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Verification Header Banner */}
      <div
        className="card"
        style={{
          padding: '18px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          borderLeft: `4px solid ${verification.status === 'passed' ? 'var(--success-text)' : 'var(--danger-text)'}`
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {verification.status === 'passed' ? (
            <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: 'var(--success-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--success-text)' }}>
              <CheckCircle2 size={22} />
            </div>
          ) : (
            <div style={{ width: 36, height: 36, borderRadius: '50%', backgroundColor: 'var(--danger-bg)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--danger-text)' }}>
              <XCircle size={22} />
            </div>
          )}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {verification.status === 'passed' ? 'Problem Verified Successfully' : 'Verification Issues Detected'}
              </h3>
              <Badge variant={verification.status === 'passed' ? 'success' : 'danger'}>
                {verification.status.toUpperCase()}
              </Badge>
            </div>
            <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
              Last executed: {new Date(verification.lastRunTimestamp || '').toLocaleString()} • Deterministic C++17 Worker
            </p>
          </div>
        </div>

        <button
          className="btn btn-secondary"
          disabled
          title="Automated re-run will execute in Phase 4"
        >
          <RefreshCw size={14} />
          <span>Rerun Suite (Phase 4)</span>
        </button>
      </div>

      {/* Metrics Row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Differential Tests
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '6px' }}>
            {verification.stressTestsPassed} / {verification.stressTestsRun}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--success-text)', marginTop: '2px' }}>
            100% equivalence Ref vs Brute
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            WA Candidates Caught
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '6px' }}>
            {verification.waCandidatesCaught} / {verification.totalWaCandidates}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Fails test suite as expected
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            TLE Candidates Timed Out
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '6px' }}>
            {verification.tleCandidatesTimedOut} / {verification.totalTleCandidates}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Exceeds time limit as intended
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
            Max Execution Telemetry
          </div>
          <div style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '6px' }}>
            {verification.executionMetrics.maxTimeMs} ms
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Peak memory: {verification.executionMetrics.maxMemoryMb} MB
          </div>
        </div>
      </div>

      {/* Compilation Matrix & Testlib Checklist */}
      <div className="card" style={{ padding: '20px' }}>
        <h4 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
          Target Compilation Matrix (g++ -std=c++17 -O3)
        </h4>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>solution.cpp</span>
            {verification.compilation.referenceSolution ? (
              <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> <span>Compiled</span>
              </span>
            ) : <span style={{ color: 'var(--danger-text)' }}>Failed</span>}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>slow.cpp</span>
            {verification.compilation.bruteForceSolution ? (
              <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> <span>Compiled</span>
              </span>
            ) : <span style={{ color: 'var(--danger-text)' }}>Failed</span>}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>validator.cpp</span>
            {verification.compilation.validator ? (
              <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> <span>Compiled</span>
              </span>
            ) : <span style={{ color: 'var(--danger-text)' }}>Failed</span>}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>checker.cpp</span>
            {verification.compilation.checker ? (
              <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> <span>Compiled</span>
              </span>
            ) : <span style={{ color: 'var(--danger-text)' }}>Failed</span>}
          </div>

          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 14px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)' }}>
            <span style={{ fontSize: '13px', fontFamily: 'var(--font-mono)' }}>gen_random.cpp</span>
            {verification.compilation.generators ? (
              <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <CheckCircle2 size={14} /> <span>Compiled</span>
              </span>
            ) : <span style={{ color: 'var(--danger-text)' }}>Failed</span>}
          </div>
        </div>
      </div>
    </div>
  );
};
