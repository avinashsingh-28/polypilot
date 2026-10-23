import React, { useState } from 'react';
import { Cpu, Terminal, FileCode, Play } from 'lucide-react';
import { Problem } from '../../types/problem';
import { CodeEditor } from '../common/CodeEditor';

interface GeneratorsTabProps {
  problem: Problem;
}

export const GeneratorsTab: React.FC<GeneratorsTabProps> = ({ problem }) => {
  const generators = problem.artifacts?.generators || [];
  const [selectedGenIndex, setSelectedGenIndex] = useState(0);

  if (generators.length === 0) {
    return (
      <div className="card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
        <Cpu size={32} style={{ margin: '0 auto 12px auto' }} />
        <h3 style={{ fontSize: '15px', color: 'var(--text-primary)', fontWeight: 600 }}>No Generators Created</h3>
        <p style={{ fontSize: '13px', marginTop: '4px' }}>
          Testlib generator code and invocation scripts will be generated in Phase 3.
        </p>
      </div>
    );
  }

  const currentGen = generators[selectedGenIndex];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* Generator Navigation */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        {generators.map((gen, idx) => (
          <button
            key={idx}
            onClick={() => setSelectedGenIndex(idx)}
            className="btn"
            style={{
              padding: '6px 12px',
              fontSize: '12px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: idx === selectedGenIndex ? 'var(--brand-primary-subtle)' : 'var(--bg-surface)',
              color: idx === selectedGenIndex ? 'var(--brand-primary)' : 'var(--text-secondary)',
              border: idx === selectedGenIndex ? '1px solid var(--brand-border)' : '1px solid var(--border-default)',
              fontWeight: idx === selectedGenIndex ? 600 : 500
            }}
          >
            <FileCode size={13} />
            <span>{gen.filename}</span>
          </button>
        ))}
      </div>

      {/* Code Editor */}
      <CodeEditor
        value={currentGen.code}
        language="cpp"
        filename={currentGen.filename}
        readOnly
        height="400px"
      />

      {/* Script Commands Box */}
      <div className="card" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '10px' }}>
          <Terminal size={15} style={{ color: 'var(--brand-primary)' }} />
          <h4 style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)' }}>
            Polygon Test Generation Script Lines (tests.cmd / tests.sh)
          </h4>
        </div>
        <div
          style={{
            backgroundColor: 'var(--bg-surface-subtle)',
            borderRadius: 'var(--radius-sm)',
            padding: '12px',
            fontFamily: 'var(--font-mono)',
            fontSize: '12px',
            color: 'var(--text-primary)',
            display: 'flex',
            flexDirection: 'column',
            gap: '6px',
            border: '1px solid var(--border-subtle)'
          }}
        >
          {currentGen.scriptCommands.map((cmd, idx) => (
            <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <span style={{ color: 'var(--text-muted)', userSelect: 'none', width: '20px' }}>{idx + 1}.</span>
              <span>{cmd}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
