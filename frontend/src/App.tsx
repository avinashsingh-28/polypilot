import React, { useState, useEffect } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { NavView } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { NewProblemPage } from './pages/NewProblemPage';
import { MyProblemsPage } from './pages/MyProblemsPage';
import { ProblemWorkspacePage } from './pages/ProblemWorkspacePage';
import { VerificationHistoryPage } from './pages/VerificationHistoryPage';
import { AIProvidersPage } from './pages/AIProvidersPage';
import { PolygonSettingsPage } from './pages/PolygonSettingsPage';
import { SettingsPage } from './pages/SettingsPage';
import { Problem } from './types/problem';
import { useProblems } from './hooks/useProblems';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('dashboard');
  const [activeProblemId, setActiveProblemId] = useState<string | null>(null);

  const { problems, loading, error, createProblem, refreshProblems, loadProblemArtifacts } = useProblems();

  const activeProblem = problems.find(p => p.id === activeProblemId) || problems[0] || null;

  useEffect(() => {
    if (activeProblem?.id) {
      loadProblemArtifacts(activeProblem.id);
    }
  }, [activeProblem?.id, loadProblemArtifacts]);

  const handleOpenProblem = (id: string) => {
    setActiveProblemId(id);
    loadProblemArtifacts(id);
    setCurrentView('workspace');
  };

  const handleCreateDraft = async (newProblem: Problem): Promise<Problem> => {
    try {
      const created = await createProblem(newProblem);
      setActiveProblemId(created.id);
      return created;
    } catch (err) {
      console.error('[App] failed to create problem:', err);
      // Fallback: add locally so UI isn't blocked if backend is down
      setActiveProblemId(newProblem.id);
      return newProblem;
    }
  };

  const renderCurrentView = () => {
    if (loading && problems.length === 0) {
      return (
        <div style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100%',
          gap: '1rem',
          color: 'var(--text-secondary)'
        }}>
          <div className="spinner" style={{
            width: 40, height: 40,
            border: '3px solid var(--border-subtle)',
            borderTopColor: 'var(--accent-primary)',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite'
          }} />
          <span>Connecting to backend…</span>
          {error && (
            <p style={{ color: 'var(--status-failed)', fontSize: '0.875rem', maxWidth: 400, textAlign: 'center' }}>
              {error} — running in offline mode.{' '}
              <button
                onClick={refreshProblems}
                style={{ color: 'var(--accent-primary)', background: 'none', border: 'none', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Retry
              </button>
            </p>
          )}
        </div>
      );
    }

    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardPage
            problems={problems}
            onNavigateNewProblem={() => setCurrentView('new-problem')}
            onOpenProblem={handleOpenProblem}
            onToggleDemoData={() => {}}
            hasDemoData={false}
          />
        );
      case 'new-problem':
        return (
          <NewProblemPage
            onCreateDraft={handleCreateDraft}
            onNavigateProblems={() => setCurrentView('my-problems')}
            onNavigateWorkspace={(id) => handleOpenProblem(id)}
          />
        );
      case 'my-problems':
        return (
          <MyProblemsPage
            problems={problems}
            onOpenProblem={handleOpenProblem}
            onNavigateNewProblem={() => setCurrentView('new-problem')}
          />
        );
      case 'workspace':
        return activeProblem ? (
          <ProblemWorkspacePage
            problem={activeProblem}
            onBack={() => setCurrentView('my-problems')}
            onRefreshProblem={loadProblemArtifacts}
          />
        ) : (
          <MyProblemsPage
            problems={problems}
            onOpenProblem={handleOpenProblem}
            onNavigateNewProblem={() => setCurrentView('new-problem')}
          />
        );
      case 'history':
        return (
          <VerificationHistoryPage
            problems={problems}
            onOpenProblem={handleOpenProblem}
          />
        );
      case 'ai-providers':
        return <AIProvidersPage />;
      case 'polygon':
        return <PolygonSettingsPage />;
      case 'settings':
        return <SettingsPage />;
      default:
        return (
          <DashboardPage
            problems={problems}
            onNavigateNewProblem={() => setCurrentView('new-problem')}
            onOpenProblem={handleOpenProblem}
            onToggleDemoData={() => {}}
            hasDemoData={false}
          />
        );
    }
  };

  return (
    <AppLayout
      currentView={currentView}
      onNavigate={setCurrentView}
      activeProblemTitle={activeProblem?.title}
      problemCount={problems.length}
    >
      {renderCurrentView()}
    </AppLayout>
  );
};

export default App;
