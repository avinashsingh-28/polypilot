import React from 'react';
import { 
  LayoutDashboard, 
  PlusCircle, 
  FolderGit2, 
  CheckCircle2, 
  Globe2, 
  Sparkles, 
  Settings as SettingsIcon,
  ChevronLeft,
  ChevronRight,
  Sun,
  Moon,
  ShieldCheck
} from 'lucide-react';
import { Logo } from '../common/Logo';

export type NavView = 
  | 'dashboard' 
  | 'new-problem' 
  | 'my-problems' 
  | 'history' 
  | 'polygon' 
  | 'ai-providers' 
  | 'settings'
  | 'workspace';

interface SidebarProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  isCollapsed: boolean;
  onToggleCollapse: () => void;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  problemCount?: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  currentView,
  onNavigate,
  isCollapsed,
  onToggleCollapse,
  theme,
  onToggleTheme,
  problemCount = 0
}) => {
  const navItems = [
    { id: 'dashboard' as NavView, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'new-problem' as NavView, label: 'New Problem', icon: PlusCircle, highlight: true },
    { id: 'my-problems' as NavView, label: 'My Problems', icon: FolderGit2, count: problemCount },
    { id: 'history' as NavView, label: 'Verification History', icon: CheckCircle2 },
    { id: 'polygon' as NavView, label: 'Polygon Integration', icon: Globe2 },
    { id: 'ai-providers' as NavView, label: 'AI Providers', icon: Sparkles },
    { id: 'settings' as NavView, label: 'Settings', icon: SettingsIcon },
  ];

  return (
    <aside
      style={{
        width: isCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)',
        backgroundColor: 'var(--bg-surface)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        transition: 'width 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
        height: '100%',
        flexShrink: 0,
        zIndex: 20
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          height: 'var(--header-height)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: isCollapsed ? 'center' : 'space-between',
          padding: isCollapsed ? '0' : '0 16px',
          borderBottom: '1px solid var(--border-subtle)'
        }}
      >
        <div 
          onClick={() => onNavigate('dashboard')} 
          style={{ cursor: 'pointer', display: 'flex', alignItems: 'center' }}
        >
          <Logo size={24} showText={!isCollapsed} />
        </div>

        {!isCollapsed && (
          <button
            onClick={onToggleCollapse}
            className="btn btn-ghost"
            style={{ padding: '4px', borderRadius: 'var(--radius-xs)' }}
            title="Collapse sidebar"
          >
            <ChevronLeft size={16} />
          </button>
        )}
      </div>

      {/* Navigation List */}
      <nav style={{ flex: 1, padding: '12px 8px', display: 'flex', flexDirection: 'column', gap: '3px', overflowY: 'auto' }}>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentView === item.id || (item.id === 'my-problems' && currentView === 'workspace');
          
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className="btn nav-item"
              data-active={isActive}
              aria-current={isActive ? 'page' : undefined}
              style={{
                width: '100%',
                justifyContent: isCollapsed ? 'center' : 'flex-start',
                padding: isCollapsed ? '9px 0' : '9px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isActive ? 'var(--brand-primary-subtle)' : 'transparent',
                color: isActive ? 'var(--brand-primary)' : 'var(--text-secondary)',
                fontWeight: isActive ? 600 : 500,
                border: 'none',
                position: 'relative'
              }}
              title={isCollapsed ? item.label : undefined}
            >
              <Icon 
                size={18} 
                style={{ 
                  color: isActive ? 'var(--brand-primary)' : item.highlight ? 'var(--brand-accent)' : 'inherit',
                  flexShrink: 0
                }} 
              />
              {!isCollapsed && (
                <span style={{ flex: 1, textAlign: 'left', fontSize: '13px', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {item.label}
                </span>
              )}
              {!isCollapsed && item.count !== undefined && item.count > 0 && (
                <span
                  style={{
                    fontSize: '11px',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-full)',
                    backgroundColor: isActive ? 'var(--brand-primary)' : 'var(--bg-surface-subtle)',
                    color: isActive ? '#ffffff' : 'var(--text-muted)',
                    fontWeight: 600
                  }}
                >
                  {item.count}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer Area */}
      <div
        style={{
          padding: '12px 10px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          flexDirection: 'column',
          gap: '8px'
        }}
      >
        {/* Expand toggle when collapsed */}
        {isCollapsed && (
          <button
            onClick={onToggleCollapse}
            className="btn btn-ghost"
            style={{ width: '100%', justifyContent: 'center', padding: '6px' }}
            title="Expand sidebar"
          >
            <ChevronRight size={16} />
          </button>
        )}

        {/* Theme Toggle */}
        <button
          onClick={onToggleTheme}
          className="btn btn-ghost"
          style={{
            width: '100%',
            justifyContent: isCollapsed ? 'center' : 'flex-start',
            padding: isCollapsed ? '8px 0' : '8px 12px',
            color: 'var(--text-secondary)'
          }}
          title={`Switch to ${theme === 'light' ? 'Dark' : 'Light'} theme`}
        >
          {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
          {!isCollapsed && (
            <span style={{ fontSize: '13px' }}>
              {theme === 'light' ? 'Dark Mode' : 'Light Mode'}
            </span>
          )}
        </button>

        {/* System Phase Status */}
        {!isCollapsed && (
          <div
            style={{
              padding: '8px 10px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'var(--bg-surface-subtle)',
              border: '1px solid var(--border-subtle)',
              fontSize: '11px',
              color: 'var(--text-muted)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '5px', fontWeight: 600, color: 'var(--text-secondary)' }}>
              <ShieldCheck size={13} style={{ color: 'var(--brand-primary)' }} />
              <span>Verified problem setting</span>
            </div>
            <div style={{ marginTop: '2px' }}>
              Polygon CP Problem Setter
            </div>
          </div>
        )}
      </div>
    </aside>
  );
};
