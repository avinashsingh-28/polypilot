import React, { useState } from 'react';
import { Code2, CheckCircle2, AlertTriangle, Clock, FileCode } from 'lucide-react';
import { Problem, ProblemSolution, SolutionTag } from '../../types/problem';
import { CodeEditor } from '../common/CodeEditor';
import { Badge } from '../common/Badge';

interface SolutionsTabProps {
  problem: Problem;
}

export const SolutionsTab: React.FC<SolutionsTabProps> = ({ problem }) => {
  const solutions = problem.artifacts?.solutions || [];
  const [selectedSolutionId, setSelectedSolutionId] = useState<string>(
    solutions[0]?.id || ''
  );

  const selectedSolution = solutions.find((s) => s.id === selectedSolutionId) || solutions[0];

  const getTagBadge = (tag: SolutionTag) => {
    switch (tag) {
      case 'main':
        return <Badge variant="primary">MAIN SOLUTION</Badge>;
      case 'accepted':
        return <Badge variant="success">BRUTE FORCE (ACCEPTED)</Badge>;
      case 'wrong-answer':
        return <Badge variant="warning">WA CANDIDATE</Badge>;
      case 'time-limit-exceeded':
        return <Badge variant="danger">TLE CANDIDATE</Badge>;
      default:
        return null;
    }
  };

  if (solutions.length === 0) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Code2 size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>No Solutions Generated</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          Solution synthesis (Reference, Brute-Force, WA candidate, TLE candidate) will be executed in Phase 3.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* File Selector Tabs */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          overflowX: 'auto',
          paddingBottom: '4px'
        }}
      >
        {solutions.map((sol) => {
          const isSelected = sol.id === selectedSolution?.id;
          return (
            <button
              key={sol.id}
              onClick={() => setSelectedSolutionId(sol.id)}
              className="btn"
              style={{
                padding: '6px 12px',
                fontSize: '12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: isSelected ? 'var(--brand-primary-subtle)' : 'var(--bg-surface)',
                color: isSelected ? 'var(--brand-primary)' : 'var(--text-secondary)',
                border: isSelected ? '1px solid var(--brand-border)' : '1px solid var(--border-default)',
                fontWeight: isSelected ? 600 : 500
              }}
            >
              <FileCode size={13} />
              <span>{sol.filename}</span>
            </button>
          );
        })}
      </div>

      {/* Selected File Details Bar */}
      {selectedSolution && (
        <div
          className="card"
          style={{
            padding: '12px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
              {selectedSolution.filename}
            </span>
            {getTagBadge(selectedSolution.tag)}
          </div>
          <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
            {selectedSolution.description}
          </span>
        </div>
      )}

      {/* Monaco Code Editor */}
      {selectedSolution && (
        <CodeEditor
          value={selectedSolution.code}
          language="cpp"
          filename={selectedSolution.filename}
          readOnly
          height="540px"
        />
      )}
    </div>
  );
};
