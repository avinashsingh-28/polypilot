import React from 'react';
import { LogOut, Plus, Search, Terminal } from 'lucide-react';
import { useAuth } from '../../auth/AuthContext';
import { NavView } from './Sidebar';
import { StatusIndicator } from '../common/StatusIndicator';

interface HeaderProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  activeProblemTitle?: string;
}

export const Header: React.FC<HeaderProps> = ({
  currentView,
  onNavigate,
  activeProblemTitle
}) => {
  const { user, logout } = useAuth();
  const getBreadcrumbs = () => {
    switch (currentView) {
      case 'dashboard':
        return <span>Dashboard</span>;
      case 'new-problem':
        return <span>New Problem</span>;
      case 'my-problems':
        return <span>My Problems</span>;
      case 'history':
        return <span>Verification History</span>;
      case 'polygon':
        return <span>Polygon Integration</span>;
      case 'ai-providers':
        return <span>AI Provider</span>;
      case 'settings':
        return <span>Settings</span>;
      case 'workspace':
        return (
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span 
              onClick={() => onNavigate('my-problems')}
              style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}
            >
              My Problems
            </span>
            <span style={{ color: 'var(--text-muted)' }}>/</span>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
              {activeProblemTitle || 'Problem Workspace'}
            </span>
          </div>
        );
      default:
        return <span>PolyPilot</span>;
    }
  };

  return (
    <header
      style={{
        height: 'var(--header-height)',
        backgroundColor: 'color-mix(in srgb, var(--bg-surface) 82%, transparent)',
        backdropFilter: 'saturate(1.6) blur(10px)',
        WebkitBackdropFilter: 'saturate(1.6) blur(10px)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        flexShrink: 0,
        position: 'relative',
        zIndex: 10
      }}
    >
      {/* Breadcrumb Title */}
      <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)' }}>
        {getBreadcrumbs()}
      </div>

      {/* Right Actions */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Environment Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '4px 10px',
            borderRadius: 'var(--radius-full)',
            backgroundColor: 'var(--bg-surface-subtle)',
            border: '1px solid var(--border-subtle)',
            fontSize: '12px'
          }}
        >
          <WorkerStatus />
        </div>

        {/* Quick Search Placeholder */}
        <div
          style={{
            position: 'relative',
            display: 'flex',
            alignItems: 'center'
          }}
        >
          <Search size={14} style={{ position: 'absolute', left: '10px', color: 'var(--text-muted)' }} />
          <input
            type="text"
            placeholder="Search problems, tags... (Ctrl+K)"
            style={{
              padding: '6px 12px 6px 30px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--border-default)',
              backgroundColor: 'var(--bg-surface-subtle)',
              fontSize: '12px',
              width: '210px',
              color: 'var(--text-primary)'
            }}
            readOnly
            disabled
            aria-label="Search (not implemented yet)"
            title="Search is not implemented yet"
          />
        </div>

        {user && (
          <button onClick={() => void logout()} className="btn btn-ghost" style={{ padding: '6px 10px', fontSize: '12px' }}
            title={`Signed in as ${user.email}`} aria-label="Sign out">
            <LogOut size={14} />
            <span>Sign out</span>
          </button>
        )}

        {/* Primary New Problem Button */}
        {currentView !== 'new-problem' && (
          <button
            onClick={() => onNavigate('new-problem')}
            className="btn btn-primary"
            style={{ padding: '6px 12px', fontSize: '13px' }}
          >
            <Plus size={15} />
            <span>Create Problem</span>
          </button>
        )}
      </div>
    </header>
  );
};

/** Live verification-worker status from the backend (not a static label). */
const WorkerStatus: React.FC = () => {
  const [state, setState] = React.useState<{ status: 'online' | 'busy' | 'offline' | 'error'; label: string }>(
    { status: 'offline', label: 'Checking worker…' });
  React.useEffect(() => {
    const base = (import.meta.env.VITE_API_URL ?? '/api/v1').replace(/\/api\/v1$/, '');
    let stop = false;
    const check = async () => {
      try {
        const r = await fetch(`${base}/health/worker`, { credentials: 'include' });
        const d = await r.json();
        if (stop) return;
        if (!r.ok || !d.workers_alive) setState({ status: 'error', label: 'Worker offline' });
        else if (!d.sandbox_available) setState({ status: 'error', label: 'Sandbox unavailable' });
        else if (d.workers_busy) setState({ status: 'busy', label: `Worker busy · ${d.queued_runs} queued` });
        else setState({ status: 'online', label: 'Worker online' });
      } catch {
        if (!stop) setState({ status: 'error', label: 'Server unreachable' });
      }
    };
    void check();
    const t = setInterval(check, 30000);
    return () => { stop = true; clearInterval(t); };
  }, []);
  return <StatusIndicator status={state.status} pulse={state.status === 'online'} label={state.label} />;
};
