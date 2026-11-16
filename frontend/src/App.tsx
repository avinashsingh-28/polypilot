import React, { useState, useEffect, lazy, Suspense } from 'react';
import { AppLayout } from './components/layout/AppLayout';
import { NavView } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
const NewProblemPage = lazy(() => import('./pages/NewProblemPage').then((m) => ({ default: m.NewProblemPage })));
import { MyProblemsPage } from './pages/MyProblemsPage';
const ProblemWorkspacePage = lazy(() => import('./pages/ProblemWorkspacePage').then((m) => ({ default: m.ProblemWorkspacePage })));
const VerificationHistoryPage = lazy(() => import('./pages/VerificationHistoryPage').then((m) => ({ default: m.VerificationHistoryPage })));
const AIProvidersPage = lazy(() => import('./pages/AIProvidersPage').then((m) => ({ default: m.AIProvidersPage })));
const PolygonSettingsPage = lazy(() => import('./pages/PolygonSettingsPage').then((m) => ({ default: m.PolygonSettingsPage })));
const SettingsPage = lazy(() => import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })));
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
    // No offline fallback: a draft that was not saved by the backend must not appear as saved.
    const created = await createProblem(newProblem);
    setActiveProblemId(created.id);
    return created;
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
              {error}{' '}
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
      <Suspense fallback={<div role="status" style={{ padding: 24, color: 'var(--text-secondary)' }}>Loading…</div>}>
        {renderCurrentView()}
      </Suspense>
    </AppLayout>
  );
};

export default App;
