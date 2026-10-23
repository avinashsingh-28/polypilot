import React, { useState } from 'react';
import { FileText, Eye, Edit3, Copy, Check } from 'lucide-react';
import { Problem } from '../../types/problem';
import { CodeEditor } from '../common/CodeEditor';

interface StatementTabProps {
  problem: Problem;
}

export const StatementTab: React.FC<StatementTabProps> = ({ problem }) => {
  const [viewMode, setViewMode] = useState<'preview' | 'source'>('preview');
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const statement = problem.artifacts?.statement;

  if (!statement) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <FileText size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>Statement Not Generated</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          This problem does not have a generated statement yet. Statement generation will be activated in Phase 3.
        </p>
      </div>
    );
  }

  const rawLatexSource = `\\begin{problem}{${problem.title}}{standard input}{standard output}{${problem.timeLimitMs / 1000} seconds}{${problem.memoryLimitMb} megabytes}

${statement.legend}

\\InputFile
${statement.inputFormat}

\\OutputFile
${statement.outputFormat}

\\Examples
${statement.samples.map((s, idx) => `\\example{
${s.input}
}{
${s.output}
}`).join('\n\n')}

\\Note
${statement.notes || 'None.'}

\\end{problem}`;

  const copySample = (text: string, index: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIndex(index);
    setTimeout(() => setCopiedIndex(null), 2000);
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* View Switcher Bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <button
            onClick={() => setViewMode('preview')}
            className={`btn ${viewMode === 'preview' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '5px 12px', fontSize: '12px' }}
          >
            <Eye size={13} />
            <span>Rendered Preview</span>
          </button>

          <button
            onClick={() => setViewMode('source')}
            className={`btn ${viewMode === 'source' ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '5px 12px', fontSize: '12px' }}
          >
            <Edit3 size={13} />
            <span>Polygon LaTeX Source</span>
          </button>
        </div>

        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Polygon-compatible statement format
        </span>
      </div>

      {viewMode === 'source' ? (
        <CodeEditor
          value={rawLatexSource}
          language="latex"
          filename="problem.tex"
          readOnly
          height="520px"
        />
      ) : (
        <div className="card" style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Title Header */}
          <div style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px', textAlign: 'center' }}>
            <h1 style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text-primary)' }}>
              {problem.title}
            </h1>
            <div style={{ display: 'flex', justifyContent: 'center', gap: '16px', fontSize: '12px', color: 'var(--text-secondary)', marginTop: '6px' }}>
              <span>Time limit: <strong>{problem.timeLimitMs / 1000}s</strong></span>
              <span>•</span>
              <span>Memory limit: <strong>{problem.memoryLimitMb}MB</strong></span>
              <span>•</span>
              <span>Input: <strong>standard input</strong></span>
              <span>•</span>
              <span>Output: <strong>standard output</strong></span>
            </div>
          </div>

          {/* Legend */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Statement
            </h3>
            <div style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
              {statement.legend}
            </div>
          </div>

          {/* Input Specification */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Input
            </h3>
            <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
              {statement.inputFormat}
            </div>
          </div>

          {/* Output Specification */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
              Output
            </h3>
            <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
              {statement.outputFormat}
            </div>
          </div>

          {/* Samples */}
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '12px' }}>
              Examples
            </h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {statement.samples.map((sample, idx) => (
                <div
                  key={idx}
                  style={{
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--radius-sm)',
                    overflow: 'hidden'
                  }}
                >
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr' }}>
                    {/* Input Col */}
                    <div style={{ borderRight: '1px solid var(--border-subtle)' }}>
                      <div
                        style={{
                          padding: '6px 12px',
                          backgroundColor: 'var(--bg-surface-subtle)',
                          fontSize: '11px',
                          fontWeight: 600,
                          color: 'var(--text-secondary)',
                          display: 'flex',
                          justifyContent: 'space-between',
                          alignItems: 'center'
                        }}
                      >
                        <span>Standard Input</span>
                        <button
                          onClick={() => copySample(sample.input, idx)}
                          className="btn btn-ghost"
                          style={{ padding: '2px', height: 'auto' }}
                        >
                          {copiedIndex === idx ? <Check size={12} style={{ color: 'var(--success-text)' }} /> : <Copy size={12} />}
                        </button>
                      </div>
                      <pre
                        style={{
                          padding: '12px',
                          margin: 0,
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          overflowX: 'auto',
                          lineHeight: 1.5
                        }}
                      >
                        {sample.input}
                      </pre>
                    </div>

                    {/* Output Col */}
                    <div>
                      <div
                        style={{
                          padding: '6px 12px',
                          backgroundColor: 'var(--bg-surface-subtle)',
                          fontSize: '11px',
                          fontWeight: 600,
                          color: 'var(--text-secondary)'
                        }}
                      >
                        Standard Output
                      </div>
                      <pre
                        style={{
                          padding: '12px',
                          margin: 0,
                          fontFamily: 'var(--font-mono)',
                          fontSize: '12px',
                          backgroundColor: 'var(--bg-surface)',
                          color: 'var(--text-primary)',
                          overflowX: 'auto',
                          lineHeight: 1.5
                        }}
                      >
                        {sample.output}
                      </pre>
                    </div>
                  </div>

                  {sample.explanation && (
                    <div
                      style={{
                        padding: '10px 12px',
                        borderTop: '1px solid var(--border-subtle)',
                        backgroundColor: 'var(--bg-surface-subtle)',
                        fontSize: '12px',
                        color: 'var(--text-secondary)',
                        whiteSpace: 'pre-line'
                      }}
                    >
                      <strong>Explanation:</strong> {sample.explanation}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* Notes */}
          {statement.notes && (
            <div>
              <h3 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '8px' }}>
                Note
              </h3>
              <div style={{ fontSize: '13px', lineHeight: 1.6, color: 'var(--text-secondary)', whiteSpace: 'pre-line' }}>
                {statement.notes}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
