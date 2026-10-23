import React, { useState } from 'react';
import { 
  FileText, 
  BookOpen, 
  Code2, 
  ShieldCheck, 
  CheckSquare, 
  Cpu, 
  Layers, 
  CheckCircle2, 
  Globe2, 
  ArrowLeft,
  Play,
  UploadCloud,
  Download,
  AlertCircle
} from 'lucide-react';
import { Problem } from '../types/problem';
import { Badge } from '../components/common/Badge';
import { OverviewTab } from '../components/workspace/OverviewTab';
import { StatementTab } from '../components/workspace/StatementTab';
import { EditorialTab } from '../components/workspace/EditorialTab';
import { SolutionsTab } from '../components/workspace/SolutionsTab';
import { ValidatorTab } from '../components/workspace/ValidatorTab';
import { CheckerTab } from '../components/workspace/CheckerTab';
import { GeneratorsTab } from '../components/workspace/GeneratorsTab';
import { TestCasesTab } from '../components/workspace/TestCasesTab';
import { VerificationTab } from '../components/workspace/VerificationTab';
import { PolygonTab } from '../components/workspace/PolygonTab';
import { Modal } from '../components/common/Modal';

export type WorkspaceTabId = 
  | 'overview' 
  | 'statement' 
  | 'editorial' 
  | 'solutions' 
  | 'validator' 
  | 'checker' 
  | 'generators' 
  | 'testcases' 
  | 'verification' 
  | 'polygon';

interface ProblemWorkspacePageProps {
  problem: Problem;
  onBack: () => void;
}

export const ProblemWorkspacePage: React.FC<ProblemWorkspacePageProps> = ({
  problem,
  onBack
}) => {
  const [activeTab, setActiveTab] = useState<WorkspaceTabId>('overview');
  const [showVerifyModal, setShowVerifyModal] = useState(false);
  const [showPublishModal, setShowPublishModal] = useState(false);

  const tabs: { id: WorkspaceTabId; label: string; icon: React.FC<{ size: number }> }[] = [
    { id: 'overview', label: 'Overview', icon: FileText },
    { id: 'statement', label: 'Statement', icon: FileText },
    { id: 'editorial', label: 'Editorial', icon: BookOpen },
    { id: 'solutions', label: 'Solutions', icon: Code2 },
    { id: 'validator', label: 'Validator', icon: ShieldCheck },
    { id: 'checker', label: 'Checker', icon: CheckSquare },
    { id: 'generators', label: 'Generators', icon: Cpu },
    { id: 'testcases', label: 'Test Cases', icon: Layers },
    { id: 'verification', label: 'Verification', icon: CheckCircle2 },
    { id: 'polygon', label: 'Polygon', icon: Globe2 },
  ];

  const renderActiveTab = () => {
    switch (activeTab) {
      case 'overview':
        return <OverviewTab problem={problem} onNavigateTab={(tab) => setActiveTab(tab as WorkspaceTabId)} />;
      case 'statement':
        return <StatementTab problem={problem} />;
      case 'editorial':
        return <EditorialTab problem={problem} />;
      case 'solutions':
        return <SolutionsTab problem={problem} />;
      case 'validator':
        return <ValidatorTab problem={problem} />;
      case 'checker':
        return <CheckerTab problem={problem} />;
      case 'generators':
        return <GeneratorsTab problem={problem} />;
      case 'testcases':
        return <TestCasesTab problem={problem} />;
      case 'verification':
        return <VerificationTab problem={problem} />;
      case 'polygon':
        return <PolygonTab problem={problem} />;
      default:
        return null;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Workspace Sub-header */}
      <div
        className="card"
        style={{
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <button
            onClick={onBack}
            className="btn btn-ghost"
            style={{ padding: '6px', borderRadius: 'var(--radius-sm)' }}
            title="Back to My Problems"
          >
            <ArrowLeft size={16} />
          </button>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <h1 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)' }}>
                {problem.title}
              </h1>
              <Badge difficulty={problem.difficulty} size="sm" />
              <Badge status={problem.status} size="sm" />
            </div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', marginTop: '2px' }}>
              {problem.slug} • {problem.preferredLanguage} • {problem.timeLimitMs}ms / {problem.memoryLimitMb}MB
            </div>
          </div>
        </div>

        {/* Global Action Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setShowVerifyModal(true)}
            className="btn btn-secondary"
            style={{ fontSize: '12px' }}
          >
            <Play size={13} style={{ color: 'var(--brand-primary)' }} />
            <span>Verify Suite</span>
          </button>

          <button
            onClick={() => setShowPublishModal(true)}
            className="btn btn-primary"
            style={{ fontSize: '12px' }}
          >
            <UploadCloud size={14} />
            <span>Publish to Polygon</span>
          </button>
        </div>
      </div>

      {/* Tabs Navigation Bar */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          borderBottom: '1px solid var(--border-subtle)',
          overflowX: 'auto',
          paddingBottom: '2px'
        }}
      >
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className="btn"
              style={{
                padding: '8px 14px',
                fontSize: '13px',
                fontWeight: isActive ? 600 : 500,
                color: isActive ? 'var(--brand-primary)' : 'var(--text-secondary)',
                borderBottom: isActive ? '2px solid var(--brand-primary)' : '2px solid transparent',
                borderRadius: '0',
                backgroundColor: 'transparent'
              }}
            >
              <Icon size={14} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* Tab Content Container */}
      <div>
        {renderActiveTab()}
      </div>

      {/* Verify Action Modal */}
      <Modal
        isOpen={showVerifyModal}
        onClose={() => setShowVerifyModal(false)}
        title="Differential Verification Suite"
        subtitle="Phase 4 Execution Pipeline"
        footer={
          <button onClick={() => setShowVerifyModal(false)} className="btn btn-secondary">
            Close
          </button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--brand-primary)', fontWeight: 600 }}>
            <AlertCircle size={18} />
            <span>Local C++ Execution Worker (Phase 4)</span>
          </div>
          <p>
            Deterministic verification will compile <code>solution.cpp</code>, <code>slow.cpp</code>, <code>validator.cpp</code>, and <code>gen_random.cpp</code> with <code>g++ -std=c++17 -O3</code>, run randomized stress tests, and feed counterexamples directly back into the automated repair loop.
          </p>
          <div style={{ padding: '10px 12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)', fontSize: '12px' }}>
            In Phase 1, you can inspect the verified execution telemetry and test cases in the <strong>Verification</strong> and <strong>Test Cases</strong> tabs.
          </div>
        </div>
      </Modal>

      {/* Publish Action Modal */}
      <Modal
        isOpen={showPublishModal}
        onClose={() => setShowPublishModal(false)}
        title="Publish to Codeforces Polygon"
        subtitle="Phase 5 Integration Pipeline"
        footer={
          <button onClick={() => setShowPublishModal(false)} className="btn btn-secondary">
            Close
          </button>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', fontSize: '13px', color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--info-text)', fontWeight: 600 }}>
            <Globe2 size={18} />
            <span>Official Polygon API Authentication (Phase 5)</span>
          </div>
          <p>
            When publishing, PolyPilot connects using your Polygon API Key & Secret with SHA-512 request signing, uploads the LaTeX statement, C++ solutions, testlib validator, and test scripts, commits the revision, and polls the package build result.
          </p>
          <div style={{ padding: '10px 12px', borderRadius: 'var(--radius-sm)', backgroundColor: 'var(--bg-surface-subtle)', fontSize: '12px' }}>
            You can configure your Polygon credentials on the <strong>Polygon Integration</strong> settings page.
          </div>
        </div>
      </Modal>
    </div>
  );
};
