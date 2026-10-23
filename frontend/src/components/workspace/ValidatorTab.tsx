import React from 'react';
import { ShieldCheck, CheckCircle2, AlertCircle } from 'lucide-react';
import { Problem } from '../../types/problem';
import { CodeEditor } from '../common/CodeEditor';

interface ValidatorTabProps {
  problem: Problem;
}

export const ValidatorTab: React.FC<ValidatorTabProps> = ({ problem }) => {
  const validator = problem.artifacts?.validator;

  if (!validator) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <ShieldCheck size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>Validator Not Generated</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          Testlib validator synthesis will be activated in Phase 3.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Bounds Checklist Bar */}
      <div
        className="card"
        style={{
          padding: '14px 18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '12px',
          backgroundColor: 'var(--bg-surface)'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <ShieldCheck size={16} style={{ color: 'var(--success-text)' }} />
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Official testlib.h Validator
          </span>
          <span
            style={{
              fontSize: '11px',
              padding: '2px 8px',
              borderRadius: 'var(--radius-full)',
              backgroundColor: 'var(--success-bg)',
              color: 'var(--success-text)',
              border: '1px solid var(--success-border)',
              fontWeight: 600
            }}
          >
            Strict Bounds Enforced
          </span>
        </div>

        <span style={{ fontSize: '12px', color: 'var(--text-secondary)' }}>
          {validator.boundsNotes}
        </span>
      </div>

      {/* Code Editor */}
      <CodeEditor
        value={validator.code}
        language="cpp"
        filename={validator.filename}
        readOnly
        height="500px"
      />

      {/* Testlib Quality Checklist */}
      <div className="card" style={{ padding: '16px 20px', backgroundColor: 'var(--bg-surface-subtle)' }}>
        <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
          Polygon testlib.h Verification Rules
        </h4>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '8px', fontSize: '12px', color: 'var(--text-secondary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={13} style={{ color: 'var(--success-text)' }} />
            <span>registerValidation(argc, argv)</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={13} style={{ color: 'var(--success-text)' }} />
            <span>Reads line breaks with readEoln()</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={13} style={{ color: 'var(--success-text)' }} />
            <span>Terminates with readEof()</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <CheckCircle2 size={13} style={{ color: 'var(--success-text)' }} />
            <span>Guarantees sum of N constraints</span>
          </div>
        </div>
      </div>
    </div>
  );
};
