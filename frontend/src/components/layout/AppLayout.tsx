import React, { useState, useEffect } from 'react';
import { Sidebar, NavView } from './Sidebar';
import { Header } from './Header';

interface AppLayoutProps {
  currentView: NavView;
  onNavigate: (view: NavView) => void;
  activeProblemTitle?: string;
  children: React.ReactNode;
  problemCount?: number;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentView,
  onNavigate,
  activeProblemTitle,
  children,
  problemCount
}) => {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    const saved = localStorage.getItem('polypilot-theme');
    return (saved as 'light' | 'dark') || 'light';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('polypilot-theme', theme);
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        width: '100vw',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-app)'
      }}
    >
      <Sidebar
        currentView={currentView}
        onNavigate={onNavigate}
        isCollapsed={isCollapsed}
        onToggleCollapse={() => setIsCollapsed(prev => !prev)}
        theme={theme}
        onToggleTheme={handleToggleTheme}
        problemCount={problemCount}
      />

      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          flex: 1,
          minWidth: 0,
          height: '100%',
          overflow: 'hidden'
        }}
      >
        <Header
          currentView={currentView}
          onNavigate={onNavigate}
          activeProblemTitle={activeProblemTitle}
        />

        <main
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '24px',
            backgroundColor: 'var(--bg-app)'
          }}
        >
          <div style={{ maxWidth: '1280px', margin: '0 auto', width: '100%' }}>
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
