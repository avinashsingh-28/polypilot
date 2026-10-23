import React, { useState } from 'react';
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
import { DEMO_PROBLEM } from './data/mockData';

export const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<NavView>('dashboard');
  const [problems, setProblems] = useState<Problem[]>([DEMO_PROBLEM]);
  const [activeProblemId, setActiveProblemId] = useState<string | null>(DEMO_PROBLEM.id);

  const activeProblem = problems.find(p => p.id === activeProblemId) || problems[0] || null;

  const handleOpenProblem = (id: string) => {
    setActiveProblemId(id);
    setCurrentView('workspace');
  };

  const handleCreateDraft = (newProblem: Problem) => {
    setProblems(prev => [newProblem, ...prev]);
    setActiveProblemId(newProblem.id);
  };

  const handleToggleDemoData = () => {
    if (problems.some(p => p.id === DEMO_PROBLEM.id)) {
      // Remove demo problem
      setProblems(prev => prev.filter(p => p.id !== DEMO_PROBLEM.id));
      if (activeProblemId === DEMO_PROBLEM.id) {
        setActiveProblemId(null);
        if (currentView === 'workspace') setCurrentView('dashboard');
      }
    } else {
      // Add demo problem
      setProblems(prev => [DEMO_PROBLEM, ...prev]);
      setActiveProblemId(DEMO_PROBLEM.id);
    }
  };

  const hasDemoData = problems.some(p => p.id === DEMO_PROBLEM.id);

  const renderCurrentView = () => {
    switch (currentView) {
      case 'dashboard':
        return (
          <DashboardPage
            problems={problems}
            onNavigateNewProblem={() => setCurrentView('new-problem')}
            onOpenProblem={handleOpenProblem}
            onToggleDemoData={handleToggleDemoData}
            hasDemoData={hasDemoData}
          />
        );
      case 'new-problem':
        return (
          <NewProblemPage
            onCreateDraft={handleCreateDraft}
            onNavigateProblems={() => setCurrentView('my-problems')}
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
            onToggleDemoData={handleToggleDemoData}
            hasDemoData={hasDemoData}
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
