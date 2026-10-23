import React from 'react';
import { 
  Plus, 
  FolderGit2, 
  CheckCircle2, 
  Globe2, 
  Clock, 
  AlertCircle, 
  ArrowRight,
  Sparkles,
  ExternalLink,
  ChevronRight,
  Database
} from 'lucide-react';
import { Problem } from '../types/problem';
import { Badge } from '../components/common/Badge';

interface DashboardPageProps {
  problems: Problem[];
  onNavigateNewProblem: () => void;
  onOpenProblem: (id: string) => void;
  onToggleDemoData: () => void;
  hasDemoData: boolean;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  problems,
  onNavigateNewProblem,
  onOpenProblem,
  onToggleDemoData,
  hasDemoData
}) => {
  const verifiedCount = problems.filter(p => p.status === 'verified').length;
  const polygonReadyCount = problems.filter(p => p.polygon?.packageBuildStatus === 'ready').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Welcome Banner */}
      <div
        className="card"
        style={{
          padding: '24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          background: 'linear-gradient(to right, var(--bg-surface), var(--bg-surface-subtle))',
          borderLeft: '4px solid var(--brand-primary)'
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
            <h1 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
              Welcome to PolyPilot
            </h1>
            <span
              style={{
                fontSize: '11px',
                fontWeight: 600,
                padding: '2px 8px',
                borderRadius: 'var(--radius-full)',
                backgroundColor: 'var(--brand-primary-subtle)',
                color: 'var(--brand-primary)'
              }}
            >
              v0.1.0-preview
            </span>
          </div>
          <p style={{ fontSize: '13px', color: 'var(--text-secondary)', maxWidth: '640px' }}>
            From problem idea to contest-ready Codeforces Polygon package. Automate statement generation, testlib validators, reference solutions, differential testing, and Polygon publishing.
          </p>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <button
            onClick={onToggleDemoData}
            className="btn btn-secondary"
            title="Toggle between fresh empty installation state and demonstration problem"
          >
            <Database size={15} />
            <span>{hasDemoData ? 'Clear Demo Problem' : 'Load Demo Problem'}</span>
          </button>

          <button
            onClick={onNavigateNewProblem}
            className="btn btn-primary"
            style={{ padding: '8px 16px', fontWeight: 600 }}
          >
            <Plus size={16} />
            <span>Create Problem</span>
          </button>
        </div>
      </div>

      {/* Metrics Grid */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
          gap: '16px'
        }}
      >
        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>TOTAL PROBLEMS</span>
            <FolderGit2 size={16} style={{ color: 'var(--brand-primary)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px' }}>
            {problems.length}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {problems.length === 0 ? 'No problems created yet' : 'In local workspace'}
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>VERIFIED PROBLEMS</span>
            <CheckCircle2 size={16} style={{ color: 'var(--success-text)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px' }}>
            {verifiedCount}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {verifiedCount === 0 ? '0 differential test passes' : 'Passed differential test suite'}
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>POLYGON PACKAGES BUILT</span>
            <Globe2 size={16} style={{ color: 'var(--info-text)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px' }}>
            {polygonReadyCount}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            {polygonReadyCount === 0 ? 'No packages deployed' : 'Synced with Codeforces Polygon'}
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <span style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>ACTIVE WORKFLOWS</span>
            <Clock size={16} style={{ color: 'var(--warning-text)' }} />
          </div>
          <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)', marginTop: '8px' }}>
            0
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Background runner idle
          </div>
        </div>
      </div>

      {/* Main Grid: Recent Projects + Activity / Alerts */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(480px, 1fr))',
          gap: '24px'
        }}
      >
        {/* Recent Projects Table */}
        <div className="card" style={{ overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          <div
            style={{
              padding: '16px 20px',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between'
            }}
          >
            <h2 style={{ fontSize: '15px', fontWeight: 600, color: 'var(--text-primary)' }}>
              Recent Problems
            </h2>
            {problems.length > 0 && (
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {problems.length} total
              </span>
            )}
          </div>

          {problems.length === 0 ? (
            <div
              style={{
                padding: '48px 24px',
                textAlign: 'center',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: '12px'
              }}
            >
              <div
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: 'var(--radius-full)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'var(--text-muted)'
                }}
              >
                <FolderGit2 size={22} />
              </div>
              <div>
                <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                  No problems in workspace
                </h3>
                <p style={{ fontSize: '13px', color: 'var(--text-secondary)', marginTop: '4px', maxWidth: '320px' }}>
                  Create your first competitive programming problem from a brief idea or load a demo problem.
                </p>
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                <button
                  onClick={onNavigateNewProblem}
                  className="btn btn-primary"
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                >
                  <Plus size={14} />
                  <span>New Problem</span>
                </button>
                <button
                  onClick={onToggleDemoData}
                  className="btn btn-secondary"
                  style={{ fontSize: '12px', padding: '6px 14px' }}
                >
                  <span>Load Demo Problem</span>
                </button>
              </div>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '13px' }}>
                <thead>
                  <tr
                    style={{
                      backgroundColor: 'var(--bg-surface-subtle)',
                      borderBottom: '1px solid var(--border-subtle)',
                      color: 'var(--text-secondary)',
                      fontSize: '11px',
                      textTransform: 'uppercase',
                      letterSpacing: '0.04em'
                    }}
                  >
                    <th style={{ padding: '10px 16px' }}>Problem Title</th>
                    <th style={{ padding: '10px 16px' }}>Difficulty</th>
                    <th style={{ padding: '10px 16px' }}>Status</th>
                    <th style={{ padding: '10px 16px' }}>Polygon Sync</th>
                    <th style={{ padding: '10px 16px', textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {problems.map((problem) => (
                    <tr
                      key={problem.id}
                      onClick={() => onOpenProblem(problem.id)}
                      style={{
                        borderBottom: '1px solid var(--border-subtle)',
                        cursor: 'pointer',
                        transition: 'background-color 0.15s ease'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                      onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                    >
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                          {problem.title}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                          {problem.slug}
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <Badge difficulty={problem.difficulty} size="sm" />
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <Badge status={problem.status} size="sm" />
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        {problem.polygon?.linked ? (
                          <span style={{ fontSize: '12px', color: 'var(--success-text)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                            <Globe2 size={13} />
                            <span>Rev {problem.polygon.latestRevision}</span>
                          </span>
                        ) : (
                          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                            Not linked
                          </span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px', textAlign: 'right' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onOpenProblem(problem.id);
                          }}
                          className="btn btn-secondary"
                          style={{ padding: '4px 10px', fontSize: '12px' }}
                        >
                          <span>Open</span>
                          <ChevronRight size={13} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Column: Tasks Requiring Attention & Quick Roadmap */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {/* Attention Box */}
          <div className="card" style={{ padding: '18px 20px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px' }}>
              <AlertCircle size={16} style={{ color: 'var(--info-text)' }} />
              <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
                System Readiness
              </h2>
            </div>
            <div style={{ fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
              PolyPilot is currently operating in <strong>Phase 1 UI Mode</strong>.
              <ul style={{ paddingLeft: '18px', marginTop: '8px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                <li>UI components, responsive layouts, and Monaco code editing are fully functional.</li>
                <li>FastAPI backend and local persistence will be wired up in <strong>Phase 2</strong>.</li>
                <li>AI specification generation will be connected in <strong>Phase 3</strong>.</li>
                <li>C++17 execution and differential stress testing runner in <strong>Phase 4</strong>.</li>
                <li>Polygon SHA-512 API publishing in <strong>Phase 5</strong>.</li>
              </ul>
            </div>
          </div>

          {/* Quick Actions Card */}
          <div className="card" style={{ padding: '18px 20px' }}>
            <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
              Recommended Next Steps
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '13px'
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Explore Problem Workspace</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Inspect all 10 artifact tabs and Monaco editor</div>
                </div>
                {problems.length > 0 ? (
                  <button
                    onClick={() => onOpenProblem(problems[0].id)}
                    className="btn btn-ghost"
                    style={{ padding: '4px 8px', fontSize: '12px', color: 'var(--brand-primary)' }}
                  >
                    <span>View</span>
                    <ArrowRight size={13} />
                  </button>
                ) : (
                  <button
                    onClick={onToggleDemoData}
                    className="btn btn-ghost"
                    style={{ padding: '4px 8px', fontSize: '12px', color: 'var(--brand-primary)' }}
                  >
                    <span>Load Demo</span>
                    <ArrowRight size={13} />
                  </button>
                )}
              </div>

              <div
                style={{
                  padding: '10px 12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '13px'
                }}
              >
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>Configure AI Provider</div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Preview model settings & BYOK architecture</div>
                </div>
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Phase 2</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
