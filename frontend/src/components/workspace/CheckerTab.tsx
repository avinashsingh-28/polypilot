import React from 'react';
import { CheckSquare, Info } from 'lucide-react';
import { Problem } from '../../types/problem';
import { CodeEditor } from '../common/CodeEditor';
import { Badge } from '../common/Badge';

interface CheckerTabProps {
  problem: Problem;
}

export const CheckerTab: React.FC<CheckerTabProps> = ({ problem }) => {
  const checker = problem.artifacts?.checker;

  if (!checker) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <CheckSquare size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>Checker Not Configured</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          Checker selection and synthesis will be configured in Phase 3.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      <div
        className="card"
        style={{
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <CheckSquare size={16} style={{ color: 'var(--brand-primary)' }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Output Checker
          </span>
          <Badge variant={checker.type === 'standard' ? 'info' : 'primary'}>
            {checker.type === 'standard' ? `Standard (${checker.standardName || 'ncmp.cpp'})` : 'Custom Testlib'}
          </Badge>
        </div>

        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          {checker.type === 'standard' 
            ? 'Numeric integer sequence comparator (ncmp.cpp) with 998244353 verification' 
            : 'Custom verification logic'}
        </span>
      </div>

      <CodeEditor
        value={checker.code}
        language="cpp"
        filename={checker.filename}
        readOnly
        height="500px"
      />
    </div>
  );
};
