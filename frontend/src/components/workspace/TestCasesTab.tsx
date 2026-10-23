import React, { useState } from 'react';
import { Layers, CheckCircle2, Eye, ShieldCheck } from 'lucide-react';
import { Problem } from '../../types/problem';
import { Badge } from '../common/Badge';
import { Modal } from '../common/Modal';

interface TestCasesTabProps {
  problem: Problem;
}

export const TestCasesTab: React.FC<TestCasesTabProps> = ({ problem }) => {
  const tests = problem.artifacts?.tests || [];
  const [selectedTest, setSelectedTest] = useState<typeof tests[0] | null>(null);

  if (tests.length === 0) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Layers size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>No Test Cases Assembled</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          Test case generation (edge cases, adversarial patterns, and random seeds) will execute in Phase 3 & 4.
        </p>
      </div>
    );
  }

  const getTypeBadge = (type: string) => {
    switch (type) {
      case 'sample':
        return <Badge variant="primary">SAMPLE</Badge>;
      case 'manual':
        return <Badge variant="info">EDGE CASE</Badge>;
      case 'random':
        return <Badge variant="default">RANDOM</Badge>;
      case 'adversarial':
        return <Badge variant="warning">ADVERSARIAL</Badge>;
      default:
        return <Badge>{type}</Badge>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Test Suite Summary Card */}
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
          <Layers size={16} style={{ color: 'var(--brand-primary)' }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Test Suite ({tests.length} cases)
          </span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--success-bg)',
              color: 'var(--success-text)',
              border: '1px solid var(--success-border)',
              fontWeight: 600,
              display: 'inline-flex',
              alignItems: 'center',
              gap: '4px'
            }}
          >
            <ShieldCheck size={12} />
            <span>All Validated</span>
          </span>
        </div>

        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          Samples, manual edge cases, and testlib script generated tests
        </span>
      </div>

      {/* Tests Table */}
      <div className="card" style={{ overflow: 'hidden' }}>
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
              <th style={{ padding: '10px 16px', width: '50px' }}>#</th>
              <th style={{ padding: '10px 16px' }}>Type</th>
              <th style={{ padding: '10px 16px' }}>Generation Command</th>
              <th style={{ padding: '10px 16px' }}>Input Preview</th>
              <th style={{ padding: '10px 16px' }}>Validator</th>
              <th style={{ padding: '10px 16px', textAlign: 'right' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {tests.map((test) => (
              <tr
                key={test.id}
                style={{
                  borderBottom: '1px solid var(--border-subtle)',
                  transition: 'background-color 0.15s ease'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <td style={{ padding: '12px 16px', fontWeight: 600, color: 'var(--text-muted)' }}>
                  {test.id}
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {getTypeBadge(test.type)}
                </td>
                <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-secondary)' }}>
                  {test.generatorCmd || 'Manual / Sample input'}
                </td>
                <td style={{ padding: '12px 16px', fontFamily: 'var(--font-mono)', fontSize: '12px', color: 'var(--text-primary)' }}>
                  <span style={{ display: 'inline-block', maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {test.inputPreview.replace(/\n/g, ' ')}
                  </span>
                </td>
                <td style={{ padding: '12px 16px' }}>
                  {test.validated ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px', color: 'var(--success-text)', fontSize: '12px', fontWeight: 500 }}>
                      <CheckCircle2 size={13} />
                      <span>Valid</span>
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>Pending</span>
                  )}
                </td>
                <td style={{ padding: '12px 16px', textAlign: 'right' }}>
                  <button
                    onClick={() => setSelectedTest(test)}
                    className="btn btn-secondary"
                    style={{ padding: '4px 10px', fontSize: '12px' }}
                  >
                    <Eye size={13} />
                    <span>View</span>
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Test Preview Modal */}
      {selectedTest && (
        <Modal
          isOpen={Boolean(selectedTest)}
          onClose={() => setSelectedTest(null)}
          title={`Test Case #${selectedTest.id}`}
          subtitle={selectedTest.generatorCmd || 'Manual / Sample input'}
          maxWidth="640px"
          footer={
            <button onClick={() => setSelectedTest(null)} className="btn btn-secondary">
              Close
            </button>
          }
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div>
              <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                INPUT
              </div>
              <pre
                style={{
                  padding: '12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'var(--bg-surface-subtle)',
                  border: '1px solid var(--border-subtle)',
                  fontFamily: 'var(--font-mono)',
                  fontSize: '12px',
                  lineHeight: 1.5,
                  maxHeight: '200px',
                  overflowY: 'auto',
                  color: 'var(--text-primary)'
                }}
              >
                {selectedTest.inputPreview}
              </pre>
            </div>

            {selectedTest.outputPreview && (
              <div>
                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
                  REFERENCE SOLUTION OUTPUT (.a)
                </div>
                <pre
                  style={{
                    padding: '12px',
                    borderRadius: 'var(--radius-sm)',
                    backgroundColor: 'var(--bg-surface-subtle)',
                    border: '1px solid var(--border-subtle)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '12px',
                    lineHeight: 1.5,
                    maxHeight: '160px',
                    overflowY: 'auto',
                    color: 'var(--text-primary)'
                  }}
                >
                  {selectedTest.outputPreview}
                </pre>
              </div>
            )}
          </div>
        </Modal>
      )}
    </div>
  );
};
