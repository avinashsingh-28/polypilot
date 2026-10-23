import React from 'react';
import { 
  Clock, 
  Cpu, 
  Layers, 
  Code2, 
  ShieldAlert, 
  CheckCircle2, 
  Globe2, 
  ArrowRight,
  Sparkles,
  Play
} from 'lucide-react';
import { Problem } from '../../types/problem';
import { Badge } from '../common/Badge';

interface OverviewTabProps {
  problem: Problem;
  onNavigateTab: (tab: string) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({ problem, onNavigateTab }) => {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Spec Card */}
      <div className="card" style={{ padding: '24px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '16px' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {problem.title}
              </h2>
              <Badge difficulty={problem.difficulty} />
              <Badge status={problem.status} />
            </div>
            <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '8px', maxWidth: '780px', lineHeight: 1.5 }}>
              {problem.shortIdea}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <button
              onClick={() => onNavigateTab('statement')}
              className="btn btn-secondary"
            >
              <span>View Statement</span>
              <ArrowRight size={14} />
            </button>
          </div>
        </div>

        {/* Key Metrics Row */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
            gap: '12px',
            marginTop: '20px',
            paddingTop: '16px',
            borderTop: '1px solid var(--border-subtle)'
          }}
        >
          <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Intended Algorithm
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
              {problem.intendedAlgorithm}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Time Limit
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Clock size={13} style={{ color: 'var(--brand-primary)' }} />
              <span>{problem.timeLimitMs} ms</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Memory Limit
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
              <Cpu size={13} style={{ color: 'var(--brand-primary)' }} />
              <span>{problem.memoryLimitMb} MB</span>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Compiler Standard
            </div>
            <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginTop: '2px' }}>
              {problem.preferredLanguage}
            </div>
          </div>
        </div>
      </div>

      {/* Workflow Execution Pipeline */}
      <div className="card" style={{ padding: '24px' }}>
        <h3 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '16px' }}>
          PolyPilot Automation Lifecycle
        </h3>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '16px' }}>
          {/* Step 1 */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)' }}>STEP 1</span>
              <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Specification Formalization
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              Formal constraints, bounds, proof sketch, and ambiguity resolution.
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 'auto' }}>Phase 3 Module</span>
          </div>

          {/* Step 2 */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)' }}>STEP 2</span>
              {problem.artifacts?.solutions.length ? (
                <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Pending</span>
              )}
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Artifact Generation
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              LaTeX statement, editorial, reference solution, testlib validator & generators.
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 'auto' }}>Phase 3 Module</span>
          </div>

          {/* Step 3 */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)' }}>STEP 3</span>
              {problem.verification?.status === 'passed' ? (
                <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Pending</span>
              )}
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Differential Verification
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              g++ C++17 compilation, differential stress tests, counterexample repair loop.
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 'auto' }}>Phase 4 Engine</span>
          </div>

          {/* Step 4 */}
          <div
            style={{
              padding: '16px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontSize: '11px', fontWeight: 700, color: 'var(--brand-primary)' }}>STEP 4</span>
              {problem.polygon?.linked ? (
                <CheckCircle2 size={16} style={{ color: 'var(--info-text)' }} />
              ) : (
                <span style={{ fontSize: '10px', color: 'var(--text-muted)' }}>Pending</span>
              )}
            </div>
            <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Polygon Publication
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
              SHA-512 API upload, commit revision, package build & caution audit.
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 'auto' }}>Phase 5 Integration</span>
          </div>
        </div>
      </div>
    </div>
  );
};
