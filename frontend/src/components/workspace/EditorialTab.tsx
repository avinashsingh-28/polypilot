import React from 'react';
import { BookOpen, Clock, Cpu, Award } from 'lucide-react';
import { Problem } from '../../types/problem';

interface EditorialTabProps {
  problem: Problem;
}

export const EditorialTab: React.FC<EditorialTabProps> = ({ problem }) => {
  const editorial = problem.artifacts?.editorial;

  if (!editorial) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <BookOpen size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>Editorial Not Generated</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          No editorial yet. Use Generate with AI (top right) to draft one.
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Complexity Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '16px' }}>
        <div className="card" style={{ padding: '16px 20px', borderLeft: '3px solid var(--brand-primary)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
            <Clock size={14} style={{ color: 'var(--brand-primary)' }} />
            <span>TIME COMPLEXITY</span>
          </div>
          <div style={{ fontSize: '14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '6px' }}>
            {editorial.complexityTime}
          </div>
        </div>

        <div className="card" style={{ padding: '16px 20px', borderLeft: '3px solid var(--info-text)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)' }}>
            <Cpu size={14} style={{ color: 'var(--info-text)' }} />
            <span>SPACE COMPLEXITY</span>
          </div>
          <div style={{ fontSize: '14px', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '6px' }}>
            {editorial.complexitySpace}
          </div>
        </div>
      </div>

      {/* Main Editorial Card */}
      <div className="card" style={{ padding: '28px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div>
          <h2 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)', marginBottom: '12px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <BookOpen size={18} style={{ color: 'var(--brand-primary)' }} />
            <span>Algorithmic Approach & Derivation</span>
          </h2>
          <div style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
            {editorial.approach}
          </div>
        </div>

        {editorial.proof && (
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '16px' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '6px' }}>
              <Award size={16} style={{ color: 'var(--success-text)' }} />
              <span>Correctness Proof</span>
            </h3>
            <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
              {editorial.proof}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
